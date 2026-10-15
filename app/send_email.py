import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import traceback

# Define your email configuration
smtp_server = "smtp.gmail.com"
smtp_port = 587
sender_email = "dinnr.dev@gmail.com"
receiver_email = "dinnr.dev@gmail.com"
password = "fdfi ypvf iwcv ngsm"


def send_message(name, user_email, user_message):
    try:
        subject = f"New Contact Form Submission from {name}"
        
        # Create the email object
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = receiver_email

        # Plain text version (fallback)
        text_message = f"""
        New Contact Form Submission:

        Name: {name}
        Email: {user_email}
        Message: 
        {user_message}

        -- End of message --
        """

        # HTML version with formatting
        html_message = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: #0046ad;">New Contact Form Submission</h2>
            <p><strong>Name:</strong> {name}</p>
            <p><strong>Email:</strong> <a href="mailto:{user_email}">{user_email}</a></p>
            <p><strong>Message:</strong></p>
            <blockquote style="background: #f9f9f9; padding: 10px; border-left: 4px solid #0046ad;">{user_message}</blockquote>
            <hr>
            <p style="font-size: 0.9em; color: #777;">This is an automated message. Please do not reply.</p>
        </body>
        </html>
        """

        # Attach both plain text and HTML versions of the email
        msg.attach(MIMEText(text_message, "plain"))  # Plain text fallback
        msg.attach(MIMEText(html_message, "html"))  # HTML content

        # Send the email
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        print("Message sent successfully.")

    except Exception as e:
        print("Message sending failed:", str(e))


if __name__ == '__main__':
    send_message('Test', 'This is a test email.', '7035817309@vtext.com')