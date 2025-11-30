# app.py
import os
import io
import re
import base64
import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
from fpdf import FPDF
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
import smtplib

# Optional translation
TRANSLATION_AVAILABLE = False
try:
    from deep_translator import GoogleTranslator
    TRANSLATION_AVAILABLE = True
except Exception:
    TRANSLATION_AVAILABLE = False

# NLTK VADER Sentiment
try:
    import nltk
    from nltk.sentiment import SentimentIntensityAnalyzer
    nltk.data.find("sentiment/vader_lexicon.zip")
except Exception:
    import nltk
    nltk.download("vader_lexicon")
from nltk.sentiment import SentimentIntensityAnalyzer

sia = SentimentIntensityAnalyzer()

# Helpers
def clean_text(text: str) -> str:
    return (
        (text or "")
        .replace("’", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("–", "-")
        .replace("—", "-")
    )

# Polishing function (improved)
def simple_polish(text: str) -> str:
    """
    Polishing: preserve paragraph breaks, expand common shorthand,
    capitalize sentences, preserve signatures, and append a polite close.
    """
    if not text:
        return ""
    # Normalize and preserve paragraph breaks
    paragraphs = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    if not paragraphs:
        return ""
    polished = "\n\n".join(paragraphs)

    # Common shorthand replacements (word boundaries, case-insensitive)
    replacements = {
        r"\bpls\b": "please",
        r"\bplz\b": "please",
        r"\basap\b": "as soon as possible",
        r"\bu\b": "you",
        r"\bthx\b": "thanks",
        r"\btnx\b": "thanks",
    }
    for pattern, repl in replacements.items():
        polished = re.sub(pattern, repl, polished, flags=re.IGNORECASE)

    # Fix spacing before punctuation
    polished = re.sub(r"\s+([.,!?;:])", r"\1", polished)

    # Capitalize first character of each paragraph and sentence starts
    def cap_sentences(par):
        par = par.strip()
        if par and par[0].islower():
            par = par[0].upper() + par[1:]
        # Capitalize after sentence-ending punctuation
        par = re.sub(r'([.!?]\s+)([a-z])', lambda m: m.group(1) + m.group(2).upper(), par)
        return par

    polished = "\n\n".join(cap_sentences(p) for p in polished.split("\n\n"))

    # Detect signature (common sign-offs) and separate it
    sig_pattern = re.compile(r"(\n\n(?:regards,|best,|sincerely,|thanks,)\s*[\w \-\.]+)$", flags=re.IGNORECASE)
    sig_match = sig_pattern.search(polished)
    if sig_match:
        signature = sig_match.group(1).strip()
        body = polished[:sig_match.start()].rstrip(".! \n")
        # Ensure polite close exists before signature
        if not re.search(r"(thank you|thanks)[\.\!]*$", body, flags=re.IGNORECASE):
            body = f"{body}.\n\nThank you."
        # Normalize signature: ensure sign-off on its own lines without trailing period
        signature = re.sub(r"[\.!\s]+$", "", signature)
        polished = f"{body}\n\n{signature}"
    else:
        # No signature: append polite close if missing
        if not re.search(r"(thank you|thanks)[\.\!]*$", polished, flags=re.IGNORECASE):
            polished = polished.rstrip(".! ")
            polished += ".\n\nThank you."

    return polished

def classify_email(text: str) -> str:
    text_lower = (text or "").lower()
    if any(word in text_lower for word in ["please", "kindly", "request", "could you"]):
        return "Request"
    elif any(word in text_lower for word in ["complain", "issue", "problem", "not happy", "unhappy"]):
        return "Complaint"
    elif any(word in text_lower for word in ["dear sir", "dear madam", "regards", "sincerely"]):
        return "Formal"
    elif any(word in text_lower for word in ["hey", "hi", "bro", "dude", "thanks a lot"]):
        return "Informal"
    else:
        return "Professional"

# Gmail API
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

def get_gmail_service():
    if not os.path.exists("token.json"):
        st.error("⚠️ token.json not found. Run authorize.py once to create it.")
        return None
    try:
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        return build("gmail", "v1", credentials=creds)
    except Exception as e:
        st.error("⚠️ Failed to load Gmail credentials.")
        st.exception(e)
        return None

def send_gmail_api(to, subject, body):
    try:
        service = get_gmail_service()
        if not service:
            return False
        msg = MIMEText(body, _charset="utf-8")
        msg["to"] = to
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True
    except HttpError as e:
        st.error("❌ Gmail API error while sending.")
        st.exception(e)
        return False
    except Exception as e:
        st.error("❌ Unexpected error while sending via Gmail API.")
        st.exception(e)
        return False

# SMTP fallback
def send_smtp(sender_email, app_password, to, subject, body):
    try:
        msg = MIMEText(body, _charset="utf-8")
        msg["From"] = sender_email
        msg["To"] = to
        msg["Subject"] = subject
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, app_password)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error("❌ SMTP send failed.")
        st.exception(e)
        return False

# Branding and PDF
BRAND_NAME = "AI Email Tone Polisher"
BRAND_TAGLINE = "Polish tone, classify intent, and send smarter emails."
LOGO_PATH = "assets/logo.png"

class BrandedPDF(FPDF):
    def header(self):
        if os.path.exists(LOGO_PATH):
            try:
                self.image(LOGO_PATH, 10, 8, 20)
            except Exception:
                pass
        self.set_xy(35, 10)
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, BRAND_NAME, ln=True)
        self.set_font("Arial", "", 10)
        self.set_xy(10, 22)
        self.cell(0, 8, BRAND_TAGLINE, ln=True)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, "Generated by AI Email Tone Polisher", 0, 0, "C")

def export_pdf(email_text, polished_text, tone_label, tone_score, email_type):
    pdf = BrandedPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0, 8, f"Original Email:\n{clean_text(email_text)}")
    pdf.ln(4)
    pdf.multi_cell(0, 8, f"Polished Email:\n{clean_text(polished_text)}")
    pdf.ln(4)
    pdf.multi_cell(0, 8, f"Tone Analysis:\nLabel: {tone_label}\nScore: {tone_score:.2f}")
    pdf.ln(4)
    pdf.multi_cell(0, 8, f"Email Type: {email_type}")
    return pdf

def download_pdf(pdf):
    pdf_bytes = pdf.output(dest="S").encode("latin-1")
    st.download_button("📄 Download PDF", pdf_bytes, file_name="email_report.pdf", mime="application/pdf")

# Session state
if "analytics" not in st.session_state:
    st.session_state.analytics = {
        "count": 0,
        "tones": {"POSITIVE": 0, "NEGATIVE": 0, "NEUTRAL": 0},
        "types": {"Formal": 0, "Informal": 0, "Complaint": 0, "Request": 0, "Professional": 0},
        "history": []
    }
if "recipient" not in st.session_state:
    st.session_state.recipient = ""
if "subject" not in st.session_state:
    st.session_state.subject = ""
if "last_polished" not in st.session_state:
    st.session_state.last_polished = ""
if "editable_polished" not in st.session_state:
    st.session_state.editable_polished = ""

# UI
st.set_page_config(page_title="AI Email Tone Polisher", page_icon="📧", layout="centered")

with st.sidebar:
    st.header("⚙️ Settings")
    language_choice = st.selectbox("🌐 Output language", ["English", "Tamil", "Hindi", "French"])
    if not TRANSLATION_AVAILABLE and language_choice != "English":
        st.warning("Translation not installed. Output will be English.\nInstall: pip install deep-translator")
        language_choice = "English"
    st.caption("Ensure token.json exists for Gmail (run authorize.py).")
    st.caption("Logo path: assets/logo.png")
    st.markdown("---")
    st.markdown("**Send options**")
    use_smtp = st.checkbox("Enable SMTP fallback (App password)", value=False)
    if use_smtp:
        st.text_input("SMTP sender email", key="smtp_sender")
        st.text_input("SMTP app password", key="smtp_app_password", type="password")
    debug_mode = st.checkbox("Show debug info", value=False)

# Header
cols = st.columns([1, 4])
with cols[0]:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, use_container_width=True)
    else:
        st.markdown("### 📧")
with cols[1]:
    st.markdown(f"<h2 style='margin-bottom:0'>{BRAND_NAME}</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:#6C63FF;margin-top:4px'>{BRAND_TAGLINE}</p>", unsafe_allow_html=True)

st.title("📧 AI Email Tone Polisher")
email_text = st.text_area("Paste your email here:", height=200, placeholder="Type or paste your email...")

col1, col2 = st.columns([1, 1])
polish_clicked = col1.button("Polish Email")
send_clicked = col2.button("Send Email")

# --- Polishing flow (auto-save editable polished text) ---
if polish_clicked:
    if email_text.strip():
        with st.spinner("Polishing and analyzing..."):
            polished_text = simple_polish(email_text)
            scores = sia.polarity_scores(polished_text)
            compound = scores["compound"]
            tone_label = "POSITIVE" if compound >= 0.05 else "NEGATIVE" if compound <= -0.05 else "NEUTRAL"
            email_type = classify_email(polished_text)
            if TRANSLATION_AVAILABLE and language_choice != "English":
                lang_map = {"English": "en", "Tamil": "ta", "Hindi": "hi", "French": "fr"}
                try:
                    polished_text = GoogleTranslator(source="auto", target=lang_map[language_choice]).translate(polished_text)
                except Exception:
                    st.warning("Translation failed; showing English output.")
            # Show editable polished text and auto-save edits to session state
            st.subheader("✨ Polished Email", divider=True)
            edited = st.text_area("Edit polished email before sending", value=polished_text, height=200, key="editable_polished")
            # Auto-save the latest edited content
            st.session_state["last_polished"] = st.session_state.get("editable_polished", edited)
            # Tone and metadata
            st.subheader("🎭 Tone Analysis", help="Sentiment analysis using VADER")
            st.markdown(f"**Label:** {tone_label}  \n**Score:** {compound:.2f}")
            st.json(scores)
            st.subheader("📂 Email Type")
            st.markdown(f"**Detected Type:** {email_type}")
            # Update analytics
            st.session_state.analytics["count"] += 1
            st.session_state.analytics["tones"][tone_label] += 1
            st.session_state.analytics["types"][email_type] += 1
            st.session_state.analytics["history"].append({
                "label": tone_label,
                "type": email_type,
                "text": email_text
            })
            pdf = export_pdf(email_text, st.session_state.get("last_polished", polished_text), tone_label, compound, email_type)
            download_pdf(pdf)
    else:
        st.error("⚠️ Please paste an email before polishing.")

# Gmail inputs
st.subheader("📤 Send via Gmail", divider=True, help="Enter recipient and subject to send polished email")
st.session_state.recipient = st.text_input("Recipient email", value=st.session_state.recipient)
st.session_state.subject = st.text_input("Subject", value=st.session_state.subject)

# --- Send handling (uses auto-saved polished text) ---
if send_clicked:
    if not st.session_state.recipient or not st.session_state.subject:
        st.error("⚠️ Please enter both recipient email and subject before sending.")
    else:
        body_to_send = st.session_state.get("last_polished") or st.session_state.get("editable_polished") or ""
        if not body_to_send.strip():
            st.error("⚠️ No polished content to send. Click 'Polish Email' first.")
        else:
            with st.spinner("Sending email..."):
                sent_ok = False
                if not use_smtp:
                    sent_ok = send_gmail_api(st.session_state.recipient, st.session_state.subject, body_to_send)
                else:
                    sender = st.session_state.get("smtp_sender", "")
                    app_pass = st.session_state.get("smtp_app_password", "")
                    if not sender or not app_pass:
                        st.error("⚠️ Provide SMTP sender email and app password in the sidebar.")
                    else:
                        sent_ok = send_smtp(sender, app_pass, st.session_state.recipient, st.session_state.subject, body_to_send)
                if sent_ok:
                    st.success("✅ Email sent successfully.")
                else:
                    st.error("❌ Email send failed. Check logs and credentials.")

# Debug info
if debug_mode:
    st.subheader("Debug")
    st.code(f"last_polished:\n{st.session_state.get('last_polished', '<empty>')}")
    st.json(st.session_state.analytics)

# Analytics dashboard
st.subheader("📊 Analytics Dashboard", divider=True, help="Visual summary of tones and email types")
st.metric("Total emails polished", st.session_state.analytics["count"])

tones = st.session_state.analytics["tones"]
labels = list(tones.keys())
values = list(tones.values())
if sum(values) == 0:
    values = [1, 0, 0]

fig1, ax1 = plt.subplots(figsize=(5, 4))
wedges, texts, autotexts = ax1.pie(
    values,
    autopct="%1.1f%%",
    startangle=90,
    pctdistance=0.75,
    textprops={"fontsize": 10}
)
ax1.axis("equal")
ax1.set_title("Tone Distribution")
ax1.legend(
    wedges,
    [f"{lbl}: {cnt}" for lbl, cnt in zip(labels, values)],
    title="Tones",
    loc="center left",
    bbox_to_anchor=(1, 0.5),
    fontsize=10
)
st.pyplot(fig1)

types = st.session_state.analytics["types"]
fig2, ax2 = plt.subplots(figsize=(6, 3))
type_labels = list(types.keys())
type_values = list(types.values())
ax2.bar(type_labels, type_values, color="skyblue")
ax2.set_title("Email Type Counts")
ax2.set_ylabel("Count")
plt.setp(ax2.get_xticklabels(), rotation=15, ha="right")
st.pyplot(fig2)

history = st.session_state.analytics["history"]
if history:
    df_hist = pd.DataFrame(history)
    df_hist["index"] = range(1, len(df_hist) + 1)
    df_counts = df_hist.groupby("index").size().reset_index(name="emails")
    df_counts = df_counts.set_index("index")
    st.line_chart(df_counts, height=180)
else:
    st.info("No usage data yet. Polish an email to populate the charts.")

# Export history CSV
st.subheader("📥 Export history", help="Download a CSV of polished emails and detected labels")
if st.button("Download history CSV"):
    if not st.session_state.analytics["history"]:
        st.warning("No history to export.")
    else:
        df = pd.DataFrame(st.session_state.analytics["history"])
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        st.download_button("⬇️ Download CSV", buf.getvalue(), file_name="polisher_history.csv", mime="text/csv")
