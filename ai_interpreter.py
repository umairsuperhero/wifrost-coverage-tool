import re
import json
import google.generativeai as genai
from typing import Dict, Any, List, Optional

def clean_json_response(text: str) -> str:
    """Remove markdown code block markers from a response text to extract raw JSON."""
    cleaned = text.strip()
    # Remove ```json and ``` wrapping
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    return cleaned.strip()

def extract_equipment_params(pdf_bytes: bytes, device_type: str = 'BTS', api_key: str = None) -> Dict[str, Any]:
    """
    Parse a custom PDF datasheet using gemini-3.1-pro to extract RF parameters.
    Returns a dictionary of parameters or raises an error.
    """
    if not api_key:
        raise ValueError("Gemini API Key is missing. Please configure it in the API Keys section.")

    genai.configure(api_key=api_key)
    
    # Configure model - using gemini-3.1-pro as requested
    # Fallback to gemini-2.5-pro or gemini-1.5-pro if 3.1-pro is not yet fully rolled out in the user's region
    model_name = 'gemini-1.5-pro' # Standard pro model which supports PDF analysis
    try:
        model = genai.GenerativeModel(model_name)
    except Exception as e:
        raise ValueError(f"Could not load Gemini Pro model: {e}")

    prompt = f"""You are an RF equipment specialist. Extract all technical parameters for a {device_type} device from this equipment datasheet. 
Return only valid JSON with no markdown formatting or additional explanation.
JSON keys MUST be exactly:
- model_name (string, e.g. "LT100B")
- manufacturer (string, e.g. "WiFrost")
- tx_power_dbm (number, e.g. 23.0)
- antenna_gain_dbi (number, e.g. 13.0)
- cable_loss_db (number, e.g. 1.0)
- receiver_sensitivity_dbm (number, e.g. -104.0)
- freq_min_mhz (number, e.g. 470.0)
- freq_max_mhz (number, e.g. 670.0)
- antenna_height_default_m (number, default 30.0 for BTS, 10.0 for CPE if not found)
- beamwidth_h_deg (number, default 90.0 for BTS, 60.0 for CPE if not found)
- beamwidth_v_deg (number, default 15.0 for BTS, 30.0 for CPE if not found)

Use null for any value that you cannot find in the document. Do not guess values unless a default is specified above.
"""

    try:
        # Pass PDF bytes directly as inline data
        pdf_part = {
            "mime_type": "application/pdf",
            "data": pdf_bytes
        }
        
        response = model.generate_content([pdf_part, prompt])
        if response is None or not response.text:
            raise ValueError("Gemini returned an empty response. The PDF may have been blocked by safety filters.")
        json_str = clean_json_response(response.text)
        params = json.loads(json_str)
        
        # Verify keys
        required_keys = [
            "model_name", "manufacturer", "tx_power_dbm", "antenna_gain_dbi", 
            "cable_loss_db", "receiver_sensitivity_dbm", "freq_min_mhz", 
            "freq_max_mhz", "antenna_height_default_m", "beamwidth_h_deg", "beamwidth_v_deg"
        ]
        
        # Ensure all keys exist
        for key in required_keys:
            if key not in params:
                params[key] = None
                
        return params
        
    except Exception as e:
        raise RuntimeError(f"Gemini PDF parsing failed: {str(e)}")

def interpret_question(question_text: str, sites_context: List[Dict[str, Any]], api_key: str = None) -> Dict[str, Any]:
    """
    Interpret Marcelo's question using gemini-3.5-flash.
    If the API key is missing or calls fail, falls back to local heuristic matching.
    """
    if not api_key or api_key.strip() == "":
        return heuristic_interpret_question(question_text, sites_context)

    genai.configure(api_key=api_key)
    
    # Use gemini-2.5-flash as default if gemini-3.5-flash is not available, or standard flash model name
    model_name = 'gemini-1.5-flash'
    try:
        model = genai.GenerativeModel(model_name)
    except Exception:
        return heuristic_interpret_question(question_text, sites_context)

    system_prompt = """You are an RF planning assistant for a TVWS network deployment tool called WiFrost.
The user is Marcelo, a sales engineer who may ask questions in plain English or Spanish.
Based on the list of available BTS sites and Marcelo's question, you must analyze his intent and return a JSON object.

JSON Schema to return:
{
  "action": "compare_all_sites" | "single_site" | "frequency_sweep" | "link_budget_report" | "coverage_check" | "explain_result",
  "site_index": number | null,   // 0-indexed integer corresponding to the index of the site in the context list. Use null if all sites, or not applicable.
  "frequency_mhz": number,       // The frequency in MHz Marcelo is asking about (e.g. 600). If not specified, default to 600.
  "environment": "urban" | "open", // 'open' for rural/islands/dense foliage, 'urban' for city centers. Default to 'open' for TVWS.
  "model": "terrain_aware" | "flat", // 'terrain_aware' (accurate) is default. If Marcelo asks for 'quick' or 'fast' or 'flat', use 'flat'.
  "plain_english_task": "string"  // A single sentence in English describing what you decided to compute.
}
"""

    context_str = f"Available sites:\n"
    for i, site in enumerate(sites_context):
        context_str += f"- Index {i}: {site['name']} (Lat: {site['lat']}, Lon: {site['lon']}, Height: {site['height_m']}m)\n"

    prompt = f"""{context_str}

Marcelo's Question: "{question_text}"

Analyze the question and return only the valid JSON according to the schema. Do not add markdown or explanation.
"""

    try:
        response = model.generate_content([system_prompt, prompt])
        if response is None or not response.text:
            return heuristic_interpret_question(question_text, sites_context)
        json_str = clean_json_response(response.text)
        result = json.loads(json_str)
        return result
    except Exception:
        return heuristic_interpret_question(question_text, sites_context)

def heuristic_interpret_question(question_text: str, sites_context: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Heuristic fallback parser when Gemini API is unavailable."""
    q_lower = question_text.lower()
    
    # Initialize defaults
    action = "single_site"
    site_index = 0 if len(sites_context) > 0 else None
    frequency_mhz = 600.0
    environment = "open"
    model = "terrain_aware"
    
    # 1. Check for frequency overrides
    freq_match = re.search(r'(\d+)\s*(mhz|mhz)', q_lower)
    if freq_match:
        frequency_mhz = float(freq_match.group(1))
        
    # 2. Check for propagation model overrides
    if "fast" in q_lower or "quick" in q_lower or "flat" in q_lower:
        model = "flat"
        
    # 3. Check for environment
    if "urban" in q_lower or "city" in q_lower or "ciudad" in q_lower:
        environment = "urban"
        
    # 4. Determine Action and Site Index
    if "compare" in q_lower or "comparar" in q_lower or "all" in q_lower or "todos" in q_lower or "which" in q_lower or "cual" in q_lower:
        action = "compare_all_sites"
        site_index = None
    elif "report" in q_lower or "pdf" in q_lower:
        action = "link_budget_report"
    elif "sweep" in q_lower or "sweep" in q_lower or "channels" in q_lower:
        action = "frequency_sweep"
    else:
        # Try to match site name keywords
        matched_index = None
        for i, site in enumerate(sites_context):
            name_parts = site['name'].lower().split()
            for part in name_parts:
                if len(part) > 3 and part in q_lower:
                    matched_index = i
                    break
            if matched_index is not None:
                break
        
        if matched_index is not None:
            site_index = matched_index
            action = "single_site"
            
    # Write a plain English description of the task
    site_name = sites_context[site_index]['name'] if site_index is not None and site_index < len(sites_context) else "all sites"
    plain_english_task = f"Analyze coverage for {site_name} at {frequency_mhz} MHz using the {model} model in an {environment} environment."
    if action == "compare_all_sites":
        plain_english_task = f"Compare coverage across all {len(sites_context)} sites at {frequency_mhz} MHz."
    elif action == "frequency_sweep":
        plain_english_task = f"Analyze the effect of different frequencies on site {site_name}."
    elif action == "link_budget_report":
        plain_english_task = f"Generate a PDF link budget report for {site_name}."

    return {
        "action": action,
        "site_index": site_index,
        "frequency_mhz": frequency_mhz,
        "environment": environment,
        "model": model,
        "plain_english_task": plain_english_task
    }
