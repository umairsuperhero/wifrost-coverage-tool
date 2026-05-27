import re
import json
import google.generativeai as genai
from typing import Dict, Any, List, Optional


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

    genai.configure(api_key=api_key)
    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
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
        response = model.generate_content([pdf_part, prompt])
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

    genai.configure(api_key=api_key)
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception:
        return heuristic_interpret_question(question_text, sites_context)

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

    context_str = "Available sites:\n"
    for i, site in enumerate(sites_context):
        context_str += f"- Index {i}: {site['name']} ({site['lat']:.5f}, {site['lon']:.5f})\n"

    prompt = f"{context_str}\nMarcelo's Question: \"{question_text}\"\nReturn only valid JSON."

    try:
        response = model.generate_content([system_prompt, prompt])
        if response is None or not response.text:
            return heuristic_interpret_question(question_text, sites_context)
        result = json.loads(clean_json_response(response.text))
        return result
    except Exception:
        return heuristic_interpret_question(question_text, sites_context)


def heuristic_interpret_question(question_text: str,
                                  sites_context: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Rule-based fallback when Gemini is unavailable."""
    q = question_text.lower()
    action = "single_site"
    site_index = 0 if sites_context else None
    frequency_mhz = 600.0
    environment = "open"
    model = "terrain_aware"

    freq_match = re.search(r'(\d+)\s*mhz', q)
    if freq_match:
        frequency_mhz = float(freq_match.group(1))

    if any(w in q for w in ["fast", "quick", "flat"]):
        model = "flat"
    if any(w in q for w in ["urban", "city", "ciudad"]):
        environment = "urban"

    if any(w in q for w in ["compare", "comparar", "all", "todos", "which", "cual", "best"]):
        action = "compare_all_sites"
        site_index = None
    elif any(w in q for w in ["report", "pdf"]):
        action = "link_budget_report"
    elif any(w in q for w in ["sweep", "channels"]):
        action = "frequency_sweep"
    elif any(w in q for w in ["cpe", "analyse", "analyze", "link", "sites"]):
        action = "single_site"
    else:
        for i, site in enumerate(sites_context):
            for part in site['name'].lower().split():
                if len(part) > 3 and part in q:
                    site_index = i
                    break

    site_name = (sites_context[site_index]['name']
                 if site_index is not None and site_index < len(sites_context)
                 else "all sites")
    plain_english_task = (
        f"Compare coverage across all {len(sites_context)} sites at {frequency_mhz} MHz."
        if action == "compare_all_sites"
        else f"Analyse coverage for {site_name} at {frequency_mhz} MHz ({model}, {environment})."
    )

    return {"action": action, "site_index": site_index,
            "frequency_mhz": frequency_mhz, "environment": environment,
            "model": model, "plain_english_task": plain_english_task}


# ── Post-simulation AI recommendation (Part 4) ────────────────────────────────

def generate_recommendation(result_dict: Dict[str, Any],
                              api_key: str = None) -> Optional[Dict[str, str]]:
    """
    Call Gemini to generate a bilingual (English + Spanish) recommendation paragraph.
    Returns {"english": "...", "spanish": "..."} or None on failure.
    """
    if not api_key or api_key.strip() == "":
        return None

    genai.configure(api_key=api_key)
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
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
        response = model.generate_content(prompt)
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
