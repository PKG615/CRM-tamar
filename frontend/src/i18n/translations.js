/**
 * Lightweight i18n dictionary. Covers the UI chrome every user sees on
 * every screen (nav, topbar, common actions, the dashboard, login) rather
 * than every string in every page — see README for exactly what's covered.
 * Keys are grouped by area; look a string up with t("area.key").
 */
export const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिंदी" },
];

export const translations = {
  en: {
    nav: {
      dashboard: "Dashboard", leads: "Leads", pipeline: "Pipeline", deals: "Deals",
      proposals: "Proposals", followups: "Follow-ups", customers: "Customers",
      reports: "Reports", campaigns: "Campaigns", assistant: "AI Assistant",
      team: "Team", settings: "Settings", logout: "Log out",
    },
    common: {
      save: "Save", cancel: "Cancel", close: "Close", add: "Add", send: "Send",
      export_csv: "Export CSV", search: "Search", loading: "Loading…", edit: "Edit",
      delete: "Delete", remove: "Remove", total: "total", previous: "Previous", next: "Next",
      language: "Language",
    },
    dashboard: {
      total_leads: "Total leads", pipeline_value: "Pipeline value", revenue_won: "Revenue won",
      overdue_followups: "Overdue follow-ups", won_lost: "Won / Lost", funnel: "Lead status funnel",
      no_leads: "No leads yet — add your first lead to see the funnel.",
    },
    login: {
      title: "LedgerCRM", sign_in_subtitle: "Sign in to your workspace",
      register_subtitle: "Set up a new workspace", forgot_subtitle: "Reset your password",
      workspace: "Workspace", email: "Email", password: "Password",
      company_name: "Company name", your_name: "Your name",
      sign_in: "Sign in", create_workspace: "Create workspace", send_reset_link: "Send reset link",
      forgot_password: "Forgot password?", new_here: "New here?", create_a_workspace: "Create a workspace",
      already_set_up: "Already set up?", back_to_sign_in: "Back to sign in",
      reset_sent: "If an account exists for that email, a reset link has been sent. Check your inbox.",
    },
  },
  hi: {
    nav: {
      dashboard: "डैशबोर्ड", leads: "लीड्स", pipeline: "पाइपलाइन", deals: "डील्स",
      proposals: "प्रस्ताव", followups: "फॉलो-अप", customers: "ग्राहक",
      reports: "रिपोर्ट्स", campaigns: "कैंपेन", assistant: "AI सहायक",
      team: "टीम", settings: "सेटिंग्स", logout: "लॉग आउट",
    },
    common: {
      save: "सेव करें", cancel: "रद्द करें", close: "बंद करें", add: "जोड़ें", send: "भेजें",
      export_csv: "CSV एक्सपोर्ट करें", search: "खोजें", loading: "लोड हो रहा है…", edit: "संपादित करें",
      delete: "हटाएं", remove: "हटाएं", total: "कुल", previous: "पिछला", next: "अगला",
      language: "भाषा",
    },
    dashboard: {
      total_leads: "कुल लीड्स", pipeline_value: "पाइपलाइन वैल्यू", revenue_won: "अर्जित राजस्व",
      overdue_followups: "बकाया फॉलो-अप", won_lost: "जीते / हारे", funnel: "लीड स्टेटस फनल",
      no_leads: "अभी कोई लीड नहीं है — फनल देखने के लिए पहली लीड जोड़ें।",
    },
    login: {
      title: "LedgerCRM", sign_in_subtitle: "अपने वर्कस्पेस में साइन इन करें",
      register_subtitle: "नया वर्कस्पेस बनाएं", forgot_subtitle: "पासवर्ड रीसेट करें",
      workspace: "वर्कस्पेस", email: "ईमेल", password: "पासवर्ड",
      company_name: "कंपनी का नाम", your_name: "आपका नाम",
      sign_in: "साइन इन करें", create_workspace: "वर्कस्पेस बनाएं", send_reset_link: "रीसेट लिंक भेजें",
      forgot_password: "पासवर्ड भूल गए?", new_here: "नए हैं?", create_a_workspace: "एक वर्कस्पेस बनाएं",
      already_set_up: "पहले से सेट अप है?", back_to_sign_in: "साइन इन पर वापस जाएं",
      reset_sent: "यदि उस ईमेल के लिए कोई खाता मौजूद है, तो एक रीसेट लिंक भेज दिया गया है। अपना इनबॉक्स जांचें।",
    },
  },
};
