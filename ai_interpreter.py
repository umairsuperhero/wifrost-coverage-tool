import re
import json
import time
import google.generativeai as genai
from typing import Dict, Any, List, Optional
import threading
_genai_lock = threading.Lock()


def _gemini_call_with_retry(model, content, max_retries=3):
    """
    Call model.generate_content() with exponential backoff.
    Retries on transient errors (429, 503, ResourceExhausted).
    Raises immediately on non-retryable errors.
    """
    retryable_signals = [
        "429", "503", "resource_exhausted",
        "quota", "rate_limit", "unavailable"
    ]

    for attempt in range(max_retries):
        try:
            response = model.generate_content(content)
            if response is None or not response.text:
                raise ValueError("Empty response from Gemini")
            return response
        except Exception as e:
            err_str = str(e).lower()
            is_retryable = any(s in err_str for s in retryable_signals)

            if is_retryable and attempt < max_retries - 1:
                wait = 2 ** attempt  # 1s, 2s, 4s
                time.sleep(wait)
                continue
            raise  # re-raise on non-retryable or final attempt


def clean_json_response(text: str) -> str:
    """Strip markdown code-block markers from a Gemini response."""
    cleaned = text.strip()
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    return cleaned.strip()


# ── PDF datasheet extraction ──────────────────────────────────────────────────

def extract_equipment_params(pdf_bytes: bytes,
                              device_type: str = 'BTS',
                              api_key: str = None) -> Dict[str, Any]:
    """Extract RF parameters from a PDF datasheet using Gemini."""
    if not api_key:
        raise ValueError("Gemini API Key is missing.")

    with _genai_lock:
        genai.configure(api_key=api_key)
    try:
        model = genai.GenerativeModel('gemini-3.1-pro')
    except Exception as e:
        raise ValueError(f"Could not load Gemini Pro model: {e}")

    prompt = f"""You are an RF equipment specialist. Extract all technical parameters
for a {device_type} device from this equipment datasheet.
Return only valid JSON with no markdown formatting or additional explanation.
JSON keys MUST be exactly:
- model_name (string)
- manufacturer (string)
- tx_power_dbm (number)
- antenna_gain_dbi (number)
- cable_loss_db (number)
- receiver_sensitivity_dbm (number)
- freq_min_mhz (number)
- freq_max_mhz (number)
- antenna_height_default_m (number, default 30.0 for BTS, 10.0 for CPE)
- beamwidth_h_deg (number, default 90.0 for BTS, 60.0 for CPE)
- beamwidth_v_deg (number, default 15.0 for BTS, 30.0 for CPE)
Use null for any value not found in the document."""

    try:
        pdf_part = {"mime_type": "application/pdf", "data": pdf_bytes}
        response = _gemini_call_with_retry(model, [pdf_part, prompt])
        if response is None or not response.text:
            raise ValueError("Gemini returned an empty response. The PDF may have been blocked by safety filters.")
        params = json.loads(clean_json_response(response.text))
        required = ["model_name", "manufacturer", "tx_power_dbm", "antenna_gain_dbi",
                    "cable_loss_db", "receiver_sensitivity_dbm", "freq_min_mhz",
                    "freq_max_mhz", "antenna_height_default_m",
                    "beamwidth_h_deg", "beamwidth_v_deg"]
        for key in required:
            if key not in params:
                params[key] = None
        return params
    except Exception as e:
        raise RuntimeError(f"Gemini PDF parsing failed: {e}")


# ── Question interpretation ───────────────────────────────────────────────────

def interpret_question(question_text: str,
                        sites_context: List[Dict[str, Any]],
                        api_key: str = None) -> Dict[str, Any]:
    """Interpret a plain-English/Spanish question using Gemini (with heuristic fallback)."""
    if not api_key or api_key.strip() == "":
        return heuristic_interpret_question(question_text, sites_context)

    with _genai_lock:
        genai.configure(api_key=api_key)
    system_prompt = """You are an RF planning assistant for WiFrost TVWS.
The user is Marcelo, a sales engineer. Analyse his question and return JSON only:
{
  "action": "compare_all_sites"|"single_site"|"frequency_sweep"|"link_budget_report"|"coverage_check"|"explain_result",
  "site_index": number|null,
  "frequency_mhz": number,
  "environment": "urban"|"suburban"|"open",
  "model": "terrain_aware"|"flat",
  "plain_english_task": "string"
}"""
    try:
        model = genai.GenerativeModel(
            'gemini-3.5-flash',
            system_instruction=system_prompt
        )
    except Exception:
        return heuristic_interpret_question(question_text, sites_context)

    context_str = "Available sites:\n"
    for i, site in enumerate(sites_context):
        context_str += f"- Index {i}: {site['name']} ({site['lat']:.5f}, {site['lon']:.5f})\n"

    try:
        response = _gemini_call_with_retry(
            model,
            f"{context_str}\n\nMarcelo's question: \"{question_text}\""
        )
        if response is None or not response.text:
            return heuristic_interpret_question(question_text, sites_context)
        result = json.loads(clean_json_response(response.text))
        return result
    except Exception:
        return heuristic_interpret_question(question_text, sites_context)


def heuristic_interpret_question(question_text: str,
                                  sites_context: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Rule-based fallback when Gemini is unavailable.
    Handles English and Colombian Spanish.
    """
    q = question_text.lower().strip()
    action = "single_site"
    site_index = 0 if sites_context else None
    frequency_mhz = 600.0
    environment = "open"
    model_type = "terrain_aware"

    # ── Frequency extraction ──────────────────────────────
    freq_match = re.search(r'(\d{3})\s*mhz', q)
    if freq_match:
        frequency_mhz = float(freq_match.group(1))

    # ── Model preference ──────────────────────────────────
    flat_keywords = ["fast", "quick", "flat", "rápido",
                     "rápida", "plano", "aproximado"]
    if any(w in q for w in flat_keywords):
        model_type = "flat"

    # ── Environment detection ─────────────────────────────
    urban_kw = ["urban", "city", "ciudad", "urbano", "urbana"]
    port_kw  = ["port", "puerto", "industrial", "muelle",
                "terminal", "container", "contenedor"]
    water_kw = ["water", "sea", "ocean", "bay", "mar", "bahía",
                "agua", "océano"]
    if any(w in q for w in port_kw):
        environment = "port_industrial"
    elif any(w in q for w in urban_kw):
        environment = "urban"
    elif any(w in q for w in water_kw):
        environment = "open_water"

    # ── Action detection (order matters — most specific first) ──

    report_kw = ["report", "pdf", "informe", "reporte",
                 "documento", "propuesta", "link budget",
                 "budget", "enlace", "presupuesto"]

    compare_kw = ["compare", "comparar", "comparación",
                  "comparison", "all sites", "todos los sitios",
                  "which", "cual", "cuál", "best", "mejor",
                  "both", "ambos", "tres sitios", "three sites",
                  "all three", "los tres"]

    sweep_kw = ["sweep", "frequency", "frecuencia", "channel",
                "canal", "700", "550", "500", "mhz",
                "que pasa si", "what if", "cambiar frecuencia",
                "change frequency", "different freq"]

    cpe_kw = ["cpe", "all cpe", "todos los cpe", "analiz",
              "analyse", "analyze", "each site", "cada sitio",
              "point", "punto", "link analysis", "análisis"]

    if any(w in q for w in report_kw):
        action = "link_budget_report"
    elif any(w in q for w in compare_kw):
        action = "compare_all_sites"
        site_index = None
    elif any(w in q for w in sweep_kw) and freq_match:
        action = "frequency_sweep"
    elif any(w in q for w in cpe_kw):
        action = "single_site"  # CPE mode triggered by heatmap.py
    else:
        # Try to match a specific site by name fragment
        for i, site in enumerate(sites_context):
            name_parts = site['name'].lower().split()
            for part in name_parts:
                if len(part) > 3 and part in q:
                    site_index = i
                    break

    # ── Plain-English task description ────────────────────
    if action == "compare_all_sites":
        task = (f"Comparing coverage across all "
                f"{len(sites_context)} sites at "
                f"{frequency_mhz:.0f} MHz.")
    elif action == "frequency_sweep":
        task = (f"Sweeping frequency range for the "
                f"selected site.")
    elif action == "link_budget_report":
        site_name = (sites_context[site_index]['name']
                     if site_index is not None
                     and site_index < len(sites_context)
                     else "selected site")
        task = f"Generating link budget report for {site_name}."
    else:
        site_name = (sites_context[site_index]['name']
                     if site_index is not None
                     and site_index < len(sites_context)
                     else "first site")
        task = (f"Analysing coverage for {site_name} at "
                f"{frequency_mhz:.0f} MHz "
                f"({model_type}, {environment}).")

    return {
        "action": action,
        "site_index": site_index,
        "frequency_mhz": frequency_mhz,
        "environment": environment,
        "model": model_type,
        "plain_english_task": task
    }


# ── Post-simulation AI recommendation (Part 4) ────────────────────────────────

def generate_recommendation(result_dict: Dict[str, Any],
                              api_key: str = None) -> Optional[Dict[str, str]]:
    """
    Call Gemini to generate a bilingual (English + Spanish) recommendation paragraph.
    Returns {"english": "...", "spanish": "..."} or None on failure.
    """
    if not api_key or api_key.strip() == "":
        return None

    with _genai_lock:
        genai.configure(api_key=api_key)
    try:
        model = genai.GenerativeModel('gemini-3.5-flash')
    except Exception:
        return None

    prompt = f"""You are an RF planning consultant writing a recommendation for a client proposal.
Given this simulation result:
{json.dumps(result_dict, indent=2, default=str)}

Write TWO short paragraphs — first in English, then in Spanish — separated by the exact string "---SPANISH---".
Each paragraph should:
- Name the recommended BTS site and explain why
- Quantify the coverage (% of area, number of CPE sites if available)
- Note any weak spots or caveats
- Suggest a practical next step
Tone: professional but clear. No jargon. Max 80 words per language.
Do not include any headers or labels."""

    try:
        response = _gemini_call_with_retry(model, prompt)
        if response is None or not response.text:
            return None
        text = response.text.strip()
        if "---SPANISH---" in text:
            parts = text.split("---SPANISH---", 1)
            return {"english": parts[0].strip(), "spanish": parts[1].strip()}
        # Fallback: return full text as English only
        return {"english": text, "spanish": ""}
    except Exception:
        return None
