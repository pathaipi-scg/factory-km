
const CONFIG = {
  // default (เผื่อ)
  N8N_WEBHOOK_URL: "http://10.28.255.19:1889/webhook/ask",

  // OEE
  N8N_OEE_URL: "http://10.28.255.19:1889/webhook/ask_oee",

  // ALARM
  N8N_ALARM_URL: "http://10.28.255.19:1889/webhook/zycoda_alarm",

  // KM
  N8N_KM_URL: "http://10.28.255.19:1889/webhook/md_pic",

  n8nMdPicUrl: "http://10.28.255.19:1889/webhook/md_pic",

  N8N_ROUTER: "http://10.28.255.19:1889/webhook/ask_router",

  N8N_ASK_KM_URL: "http://10.28.255.19:1889/webhook/ask_km",

  // Summarize a trained KM's Slide Analysis into a short overview file.
  N8N_SUMMARY_URL: "http://10.28.255.19:1889/webhook/md_summary",

  // Split a Morning Talk KM's Slide Analysis into CB/Jarvis cases (returns JSON).
  N8N_CASES_URL: "http://10.28.255.19:1889/webhook/md_cases",

  STORE_KEY: "scg_multi_chat",
  CURRENT_KEY: "scg_current_chat"
};

module.exports = CONFIG;

