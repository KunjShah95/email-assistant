import streamlit as st
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import tempfile
import os
import time
import json
import re
from PyPDF2 import PdfReader
import requests
import traceback
from dotenv import load_dotenv
from pathlib import Path  # new import for .env path handling

# Load environment variables from .env explicitly using current file directory
dotenv_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

# 🌟 Streamlit UI config
st.set_page_config(page_title="ResumeMailer AI", layout="centered")
st.title("📧 AI-Powered Resume Emailer")
st.markdown(
    "Send personalized job application emails to HRs using your resume + Groq AI."
)

# 📾 Step 1: Upload Resume
st.header("1. Upload Resume (PDF)")
resume_file = st.file_uploader("Upload your resume (PDF only)", type=["pdf"])

# 📧 Step 2: Your Email
st.header("2. Your Email Credentials")
sender_email = st.text_input("Your Gmail ID", value="")
sender_password = st.text_input("Gmail App Password", value="", type="password")
st.caption(
    "⚠️ Note: You need to use an App Password, not your regular Gmail password. [Learn how to create an App Password](https://support.google.com/accounts/answer/185833)"
)

# Add test email functionality
test_email = st.checkbox("🧪 Test your email configuration")
if test_email:
    test_recipient = st.text_input(
        "Enter your email to receive a test message", value=sender_email
    )
    if st.button("🧪 Send Test Email"):
        if not sender_email or not sender_password:
            st.error("❌ Please enter your Gmail ID and App Password first.")
        elif not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", test_recipient):
            st.error("❌ Invalid test recipient email format.")
        else:
            try:
                msg = MIMEMultipart()
                msg["Subject"] = "Test Email from Resume Mailer App"
                msg["From"] = sender_email
                msg["To"] = test_recipient

                # Add body
                test_body = "This is a test email to verify your email configuration is working correctly. If you received this, your setup is correct!"
                msg.attach(MIMEText(test_body, "plain"))

                with st.spinner("📤 Sending test email..."):
                    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                        server.login(sender_email, sender_password)
                        server.sendmail(sender_email, test_recipient, msg.as_string())

                st.success("✅ Test email sent successfully! Please check your inbox.")
            except smtplib.SMTPAuthenticationError:
                st.error(
                    "❌ Authentication failed. Please check your Gmail ID and App Password."
                )
            except Exception as e:
                st.error(f"❌ Failed to send test email: {e}")

# 👤 Step 3: HR Email(s)
st.header("3. HR Email(s)")
hr_emails = st.text_input(
    "Enter HR Email(s) (comma-separated)",
    placeholder="hr1@company.com, hr2@example.com",
)
st.caption(
    "Multiple emails can be entered, separated by commas. Each recipient will receive a separate email."
)
# New: CC & BCC inputs
cc_emails = st.text_input("CC Email(s) (comma-separated)", value="")
bcc_emails = st.text_input("BCC Email(s) (comma-separated)", value="")

# 💼 Step 4: Optional Job Description
st.header("4. Job Description")
job_description = st.text_area("Paste the job description (optional)", height=150)

# 📧 Step 5: Email Subject
st.header("5. Email Subject")
email_subject = st.text_input("Email Subject", value="Job Application: Resume Attached")
st.caption("Customize your email subject line to make it more specific to the position")

# 🔑 Step 6: Groq API Key (override optional)
st.header("6. Groq API Key")
api_key_input = st.text_input(
    "Paste your Groq API Key (or leave blank to use .env)", type="password"
)
groq_api_key = api_key_input.strip() or os.getenv("GROQ_API_KEY", "")
if not groq_api_key:
    st.error("❌ No Groq API key provided. Please set it in .env or paste above.")
elif not re.match(r"^gsk_[A-Za-z0-9]{20,}$", groq_api_key):
    st.error(
        "❌ Groq API key format looks invalid. Key must start with 'gsk_' and be at least 20 characters."
    )

# ▶️ Submit Button
if groq_api_key and groq_api_key.startswith("gsk_"):
    submit = st.button("🔍 Generate & Send Email")
else:
    st.error("🔒 Please provide a valid Groq API key to enable email generation.")
    submit = False


# 📄 Extract text from PDF
@st.cache_data
def extract_pdf_text(pdf_file):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_file.getvalue())
            reader = PdfReader(tmp.name)
            text = "\n".join(
                page.extract_text() for page in reader.pages if page.extract_text()
            )
        os.unlink(tmp.name)
        return text
    except Exception as e:
        st.error(f"❌ Error extracting PDF text: {e}")
        return ""


# 🤖 Generate email using Groq API
def generate_email_from_resume(resume_text, job_desc, subject, api_key):
    if not api_key:
        return "❌ No API key provided. Cannot generate email."

    prompt = f"""
You are a career assistant. Draft a professional job application email.
Use the following RESUME and JOB DESCRIPTION:

RESUME:
{resume_text[:4000]}

JOB DESCRIPTION:
{job_desc if job_desc else "General position application"}

EMAIL SUBJECT:
{subject}

Requirements:
- Keep the email professional and concise
- Highlight relevant skills from the resume
- Mention that the resume is attached
- Include a proper greeting and closing
- Make it personalized but not overly casual
"""

    try:
        payload = {
            "model": "llama3-8b-8192",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1000,
            "temperature": 0.7,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=30,
        )

        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        elif response.status_code == 401:
            st.error(
                "❌ Groq API Error 401: Invalid API key. Using fallback email template."
            )
            fallback_email = (
                "Hello,\n\n"
                "I am writing to apply for the position. Please find my resume attached.\n\n"
                "Thank you for your time and consideration.\n\n"
                "Best regards,\nApplicant"
            )
            return fallback_email
        else:
            st.error(f"❌ Groq API Error: {response.status_code} - {response.text}")
            return (
                "❌ Failed to generate email. Please check your API key and try again."
            )

    except requests.exceptions.Timeout:
        st.error("❌ Request timed out. Please try again.")
        return "❌ Request timed out. Please try again."
    except Exception as e:
        st.error(f"❌ Groq API Error: {e}")
        return "❌ Failed to generate email. Please check your connection and API key."


# 📧 Email sender function with extensive debugging
def send_email(to_email, subject, body, pdf_file, from_email, password):
    debug_info = []
    try:
        debug_info.append("🔍 DEBUG: Starting email send process")
        debug_info.append(f"🔍 DEBUG: Recipient: {to_email}")
        debug_info.append(f"🔍 DEBUG: Sender: {from_email}")
        debug_info.append(f"🔍 DEBUG: Subject: {subject}")
        debug_info.append(f"🔍 DEBUG: Body length: {len(body)} characters")
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email
        msg.attach(MIMEText(body, "plain"))
        pdf_file.seek(0)
        pdf_data = pdf_file.getvalue()
        debug_info.append(f"🔍 DEBUG: PDF size: {len(pdf_data)} bytes")
        pdf_attachment = MIMEApplication(pdf_data, Name="resume.pdf")
        pdf_attachment["Content-Disposition"] = 'attachment; filename="resume.pdf"'
        msg.attach(pdf_attachment)
        debug_info.append("🔍 DEBUG: PDF attachment added successfully")
        debug_info.append("🔍 DEBUG: Connecting to Gmail SMTP server...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            debug_info.append("🔍 DEBUG: SMTP connection established")
            debug_info.append("🔍 DEBUG: Attempting login...")
            server.login(from_email, password)
            debug_info.append("🔍 DEBUG: Login successful")
            debug_info.append("🔍 DEBUG: Sending message...")
            server.sendmail(from_email, to_email, msg.as_string())
            debug_info.append(f"🔍 DEBUG: Message sent successfully to {to_email}")
        with st.expander("🔍 Debug Information", expanded=True):
            st.text("\n".join(debug_info))
        return True, "Email sent successfully"
    except smtplib.SMTPAuthenticationError as e:
        error_msg = f"Authentication failed: {str(e)}"
        debug_info.append(f"❌ ERROR: {error_msg}")
        with st.expander("🔍 Debug Information", expanded=True):
            st.text("\n".join(debug_info))
        return False, error_msg
    except smtplib.SMTPRecipientsRefused as e:
        error_msg = f"Recipient {to_email} refused: {str(e)}"
        debug_info.append(f"❌ ERROR: {error_msg}")
        with st.expander("🔍 Debug Information", expanded=True):
            st.text("\n".join(debug_info))
        return False, error_msg
    except smtplib.SMTPException as e:
        error_msg = f"SMTP error: {str(e)}"
        debug_info.append(f"❌ ERROR: {error_msg}")
        with st.expander("🔍 Debug Information", expanded=True):
            st.text("\n".join(debug_info))
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        debug_info.append(f"❌ ERROR: {error_msg}")
        debug_info.append(f"❌ TRACEBACK: {traceback.format_exc()}")
        with st.expander("🔍 Debug Information", expanded=True):
            st.text("\n".join(debug_info))
        return False, error_msg


# 🚀 Main Action
if submit:
    missing_fields = []
    if not resume_file:
        missing_fields.append("Resume file")
    if not sender_email:
        missing_fields.append("Gmail ID")
    if not sender_password:
        missing_fields.append("Gmail App Password")
    if not hr_emails:
        missing_fields.append("HR Email(s)")
    if missing_fields:
        st.warning(
            f"⚠️ Please fill in the following required fields: {', '.join(missing_fields)}"
        )
    else:
        email_pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        if not re.match(email_pattern, sender_email):
            st.error(
                "❌ Invalid sender email format. Please enter a valid email address."
            )
        else:
            hr_email_list = [
                email.strip() for email in hr_emails.split(",") if email.strip()
            ]
            invalid_emails = [
                email for email in hr_email_list if not re.match(email_pattern, email)
            ]
            if invalid_emails:
                st.error(f"❌ Invalid HR email format: {', '.join(invalid_emails)}")
            else:
                with st.spinner("📄 Extracting resume text..."):
                    resume_text = extract_pdf_text(resume_file)
                if not resume_text:
                    st.error(
                        "❌ Failed to extract text from resume. Please check your PDF file."
                    )
                else:
                    with st.spinner("🤖 Generating email with AI..."):
                        email_body = generate_email_from_resume(
                            resume_text, job_description, email_subject, groq_api_key
                        )
                    if email_body and not email_body.startswith("❌"):
                        st.success("📬 Email generated successfully!")
                        st.subheader("📄 Email Preview (Editable)")
                        # Editable email body
                        edited_email_body = st.text_area(
                            "Edit Email Content before sending:",
                            email_body,
                            height=300,
                            key="editable_email_body",
                        )
                        # Download button for generated email
                        st.download_button(
                            label="💾 Download Email as TXT",
                            data=edited_email_body,
                            file_name="generated_email.txt",
                            mime="text/plain",
                        )
                        st.subheader("📤 Send Emails")
                        st.write(f"*Recipients:* {', '.join(hr_email_list)}")
                        st.write(f"*Subject:* {email_subject}")
                        confirm_send = st.checkbox(
                            "✅ I confirm that I want to send this email to the above recipients"
                        )
                        # More prominent send button
                        send_emails_now = st.button(
                            "🚀🚀 SEND EMAILS NOW 🚀🚀",
                            type="primary",
                            help="Click to send emails to all recipients.",
                        )
                        if confirm_send and send_emails_now:
                            success_count = 0
                            total_emails = len(hr_email_list)
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            st.subheader("🔍 Email Sending Debug")
                            debug_container = st.container()
                            sent_log = []  # For logging sent emails
                            for i, hr_email in enumerate(hr_email_list):
                                with debug_container:
                                    st.write(f"📧 *Sending to {hr_email}...*")
                                    status_text.text(
                                        f"📤 Processing email {i + 1}/{total_emails}: {hr_email}"
                                    )
                                    with st.expander(
                                        f"📋 Email Details for {hr_email}",
                                        expanded=False,
                                    ):
                                        st.text(f"From: {sender_email}")
                                        st.text(f"To: {hr_email}")
                                        st.text(f"Subject: {email_subject}")
                                        st.text(
                                            f"Body Length: {len(edited_email_body)} characters"
                                        )
                                        st.text(
                                            f"PDF Size: {len(resume_file.getvalue())} bytes"
                                        )
                                resume_file.seek(0)
                                success, message = send_email(
                                    hr_email,
                                    email_subject,
                                    edited_email_body,
                                    resume_file,
                                    sender_email,
                                    sender_password,
                                )
                                sent_log.append(
                                    {
                                        "to": hr_email,
                                        "subject": email_subject,
                                        "success": success,
                                        "message": message,
                                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                                    }
                                )
                                with debug_container:
                                    if success:
                                        st.success(
                                            f"✅ *SUCCESS*: Email sent to {hr_email}"
                                        )
                                        success_count += 1
                                    else:
                                        st.error(f"❌ *FAILED*: {hr_email} - {message}")
                                progress_bar.progress((i + 1) / total_emails)
                                time.sleep(2)
                            status_text.text("")
                            progress_bar.empty()
                            # Show summary and log
                            st.subheader("📊 Email Send Summary")
                            st.write(
                                f"Total: {total_emails}, Success: {success_count}, Failed: {total_emails - success_count}"
                            )
                            st.json(sent_log)
                            # Save log to file
                            with open("sent_email_log.json", "a") as logf:
                                for entry in sent_log:
                                    logf.write(json.dumps(entry) + "\n")
                            if success_count == total_emails:
                                st.balloons()
                                st.success(
                                    f"🎉 All {success_count} emails sent successfully!"
                                )
                            else:
                                st.warning(
                                    f"⚠️ {success_count} out of {total_emails} emails sent successfully."
                                )
                    else:
                        st.error(
                            "❌ Failed to generate email. Please check your API key and try again."
                        )

# Footer
st.markdown("---")
st.markdown("💡 *Tips:*")
st.markdown("- Use a specific email subject for better response rates")
st.markdown("- Keep your resume updated and relevant")
st.markdown("- Test your email configuration before sending to multiple recipients")
st.markdown("- Save frequently used email templates for quick reuse")
