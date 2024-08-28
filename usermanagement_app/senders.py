import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from USER_MANAGEMENT import settings
from usermanagement_app.flags import PLATFORM_ACTIVE
from usermanagement_app.models import MailORSMS, MappedURls, NotificationLog, MemberPlatform, Platform
from usermanagement_app.utils import password_hash, replace_user_values_in_template


class OTPSendMailNotification(threading.Thread):
    def __init__(self, member, member_otp=None, magic_link_url=None, member_platform=None, project_name=None,
                 reset_password=True, template_string=None):
        self.member_otp = member_otp
        self.member = member
        self.magic_link_url = magic_link_url
        self.member_platform = member_platform
        self.project_name = project_name
        self.reset_password = reset_password
        self.template_string = template_string
        threading.Thread.__init__(self)

    def run(self) -> None:
        try:
            type = "ForgetPassword_Setup"
            subject = self.project_name
            message = "Something Went Wrong"
            member_platform = self.member_platform
            if not self.member:
                return "Member not found"
            email = self.member.email_id

            mail_to = email
            recipients = [mail_to]
            html_message = ''
            if self.member_otp:
                otp = self.member_otp.otp
                context = {'user_name': email,
                           'otp': otp,
                           "project_name": self.project_name}
                subject = f'Reg: {self.project_name} OTP'
                type = 'Mail_Otp'
                html_message = mark_safe(render_to_string('email/otp_trigger.html', context))
            if self.magic_link_url:
                context = {'user_name': email,
                           'magic_link_url': self.magic_link_url,
                           "project_name": self.project_name}
                if self.reset_password:
                    subject = f'Reset password for your account in {self.project_name}'
                else:
                    if self.member_platform:
                        platform_name = self.member_platform.platform_id.name
                    else:
                        platform_name = "NA"
                    subject = f'Set-up your {platform_name} account to collaborate with {self.project_name}'

                if self.reset_password:
                    html_message = mark_safe(render_to_string('email/password_set.html', context))
                else:
                    if platform_name != "NA":
                        logo = self.member_platform.platform_id.logo
                        if logo:
                            logo = logo.url
                            context['logo'] = logo
                        else:
                            context['logo'] = "https://app.leadcircle.ai/assets/images/newLogo.png"
                    context['message'] = mark_safe('''<p>Hello ${user:name}</p>,
                               <p>${company:company_name} has invited you to collaborate in Lead circle.</p> 
                               <p>Use the below link to set up your account and get started</p>
                               <p><a href={{magic_link_url}}>Let's Get Started</a></p>
                                <br>
                                <p>Best Regards,</p>
                            <p>${company:company_name}</p>'''.replace('{{magic_link_url}}', self.magic_link_url))
                    html_message = replace_user_values_in_template(
                        render_to_string('email/new_user_account_setup.html', context),
                        self.member_platform.memberinformation_id)

            member_information_id = None
            if self.member_platform:
                if isinstance(self.member_platform, MemberPlatform):
                    member_information_id = self.member_platform.memberinformation_id
                else:
                    try:
                        member_platform = MemberPlatform.objects.get(pk=self.member_platform)
                        member_information_id = member_platform.memberinformation_id
                    except:
                        member_information_id = None

            message = replace_user_values_in_template(message, memberinformation=member_information_id,
                                                      email_id=str(settings.DEFAULT_FROM_EMAIL), name=self.project_name)
            html_message = replace_user_values_in_template(html_message, memberinformation=member_information_id,
                                                           email_id=str(settings.DEFAULT_FROM_EMAIL),
                                                           name=self.project_name)

            send_mail(
                subject=subject,
                message=message,
                html_message=html_message,
                from_email=str(settings.DEFAULT_FROM_EMAIL),
                recipient_list=recipients,
            )
            mail = MailORSMS.objects.create(send_to=mail_to, send_from=str(settings.DEFAULT_FROM_EMAIL),
                                            subject=subject, message=message, type=type)
            if member_platform and self.member:
                NotificationLog.objects.create(member_id=self.member, mailorsms_id=mail,
                                               memberplatform_id=member_platform, memberotp_id=self.member_otp)
        except Exception as e:
            print("msg:", str(e))
            return


# class OTPPasswordNotification(threading.Thread):
#     def __init__(self, member=None, password=None):
#         self.member = member
#         self.password = password
#         threading.Thread.__init__(self)
#
#     def run(self) -> None:
#         try:
#             type = "Password_Setup"
#             subject = "User Credentials"
#             message = ""
#             if not self.member:
#                 return "Member not found"
#             email = self.member.email_id
#
#             mail_to = email
#             recipients = [mail_to]
#             html_message = ''
#             if self.password:
#                 context = {'user_name': email,
#                            'password': self.password
#                            }
#                 subject = "User Credentials"
#                 type = 'Mail_Otp'
#                 html_message = mark_safe(render_to_string('email/otp_trigger.html', context))
#
#             send_mail(
#                 subject=subject,
#                 message=message,
#                 html_message=html_message,
#                 from_email=str(settings.DEFAULT_FROM_EMAIL),
#                 recipient_list=recipients,
#             )
#
#         except Exception as e:
#             print("msg:", str(e))
#             return


class PasswordNotification(threading.Thread):
    def __init__(self, member=None, random_password=None):
        self.member = member
        self.random_password = random_password
        threading.Thread.__init__(self)

    def run(self) -> None:
        try:
            subject = "Welcome to Our Platform!"
            message = ""
            if not self.member:
                return "Member not found"
            email = self.member.email_id

            mail_to = email
            recipients = [mail_to]
            html_message = ''
            if self.random_password:
                context = {'user_name': email,
                           'password': self.random_password,

                           }
                html_message = mark_safe(render_to_string('email/password_send.html', context))

            message = replace_user_values_in_template(message, email_id=str(settings.DEFAULT_FROM_EMAIL),
                                                      name="Platform")
            html_message = replace_user_values_in_template(html_message,
                                                           email_id=str(settings.DEFAULT_FROM_EMAIL),
                                                           name="Platform")

            send_mail(
                subject=subject,
                message=message,
                html_message=html_message,
                from_email=str(settings.DEFAULT_FROM_EMAIL),
                recipient_list=recipients,
            )

        except Exception as e:
            print("msg:", str(e))
            return


class MemberCreateMailNotification(threading.Thread):
    def __init__(self, domain_url, password_decode, member_platform, member_information, member, login_url,
                 company_name):
        self.password_decode = password_decode
        self.domain_url = domain_url
        self.member_platform = member_platform
        self.member = member
        self.member_information = member_information
        self.company_name = company_name
        self.login_url = login_url
        threading.Thread.__init__(self)

    def run(self) -> None:
        global html_message
        try:
            type = "Member Create"
            subject = "User Management - Member Create"
            message = "Something Went Wrong"
            if not self.member_information:
                return "Member not found"
            email = self.member_information.email_id
            mail_to = email
            recipients = [mail_to]
            if self.password_decode and email:
                context = {'user_name': email,
                           'user_password': self.password_decode,
                           'company_name': self.company_name,
                           'login_url': self.login_url}
                subject = 'Reg: User Management Member Create'

                html_message = mark_safe(render_to_string('email/member_create_template.html', context))
                html_message = replace_user_values_in_template(html_message, self.member_information)

            send_mail(
                subject=subject,
                message=message,
                html_message=html_message,
                from_email=str(settings.DEFAULT_FROM_EMAIL),
                recipient_list=recipients,
            )
            mail = MailORSMS.objects.create(send_to=mail_to, send_from=str(settings.DEFAULT_FROM_EMAIL),
                                            subject=subject, message=message, type=type)
            if self.member_platform and self.member:
                log = NotificationLog.objects.create(member_id=self.member, mailorsms_id=mail,
                                                     memberplatform_id=self.member_platform)

        except Exception as e:
            print("msg:", str(e))
            return


class SendDefaultMailNotification(threading.Thread):
    def __init__(self, subject, email, message, member_platform_id, audio_url, company_name, content, type=None,
                 name=None):
        threading.Thread.__init__(self)
        self.subject = subject
        # self.subject = subject
        self.email = email
        self.message = message
        self.member_platform_id = member_platform_id
        self.company_name = company_name
        self.audio_url = audio_url
        self.content = content
        self.name = name

    def run(self) -> None:
        try:
            # type = self.type
            subject = self.subject
            message = self.message
            email = self.email
            audio_url = self.audio_url
            content = self.content
            company_name = self.company_name
            name = self.name
            # if not self.type:
            #     type = "General Reminder"
            # if not type:
            #     subject = "General Reminder"
            if not message:
                message = "Something Went Wrong"
            recipients = [email]
            if recipients:
                context = {'user_name': name if name else email,
                           'audio_url': audio_url,
                           'content': mark_safe(content),
                           'company_name': company_name}
                html_message = mark_safe(render_to_string('email/default_notification_template.html', context))

                member_information_id = None
                if self.member_platform_id:
                    if isinstance(self.member_platform_id, MemberPlatform):
                        member_information_id = self.member_platform_id.memberinformation_id
                    else:
                        try:
                            member_platform = MemberPlatform.objects.get(pk=self.member_platform_id)
                            member_information_id = member_platform.memberinformation_id
                        except:
                            member_information_id = None

                message = replace_user_values_in_template(message, memberinformation=member_information_id,
                                                          email_id=str(settings.DEFAULT_FROM_EMAIL), name=company_name)
                html_message = replace_user_values_in_template(html_message, memberinformation=member_information_id,
                                                               email_id=str(settings.DEFAULT_FROM_EMAIL),
                                                               name=company_name)

                send_mail(
                    subject=subject,
                    message=message,
                    html_message=html_message,
                    from_email=str(settings.DEFAULT_FROM_EMAIL),
                    recipient_list=recipients,
                )
                print("send_mail")
            # mail = MailORSMS.objects.create(send_to=email, send_from=str(settings.DEFAULT_FROM_EMAIL),
            #                                 subject=subject, message=message, type=type)
            # if self.member_platform and self.member:
            #     log = NotificationLog.objects.create(member_id=self.member, mailorsms_id=mail,
            #                                          memberplatform_id=self.member_platform)

        except Exception as e:
            print("msg:", str(e))
            return


class SendEmailNotification(threading.Thread):
    def __init__(self, subject, email, name, message, template, company_name, request=None, platform_logo=None):
        threading.Thread.__init__(self)
        self.subject = subject
        self.email = email
        self.name = name
        self.message = message
        self.template = template
        self.company_name = company_name
        self.request = request
        self.platform_logo = platform_logo

    def run(self) -> None:
        try:
            subject = self.subject
            email = self.email
            name = self.name
            message = self.message
            template = self.template
            company_name = self.company_name
            request = self.request

            recipients = [email]
            for recipient in recipients:
                context = {'user_name': name if name else recipient,
                           'message': mark_safe(message),
                           'company_name': company_name, 'platform_logo': self.platform_logo}
                html_message = mark_safe(render_to_string(f'email/{template}.html', context))

                message = replace_user_values_in_template(message, email_id=str(settings.DEFAULT_FROM_EMAIL),
                                                          name=company_name)
                html_message = replace_user_values_in_template(html_message, email_id=str(settings.DEFAULT_FROM_EMAIL),
                                                               name=company_name)

                smtp_host = request.data.get('smtp_host')
                smtp_port = request.data.get('smtp_port')
                smtp_user = request.data.get('smtp_user')
                smtp_password = request.data.get('smtp_password')
                from_email = request.data.get('from_email')
                from_name = request.data.get('from_name')

                if smtp_user and smtp_password and smtp_host and smtp_port:
                    with smtplib.SMTP(smtp_host, smtp_port) as server:
                        mime = MIMEMultipart()
                        server.starttls()
                        server.login(smtp_user, smtp_password)
                        mime['subject'] = self.subject
                        mime['to'] = str(email)
                        mime['from'] = str(smtp_user) if not from_name else from_name
                        mime.attach(MIMEText(html_message, 'html'))
                        # Send the email
                        print("mime as string", mime.as_string())
                        server.sendmail(from_email, email, msg=mime.as_string())
                        response = server.noop()
                        if response[0] == 250:  # 250 is a success response code
                            print("Email accepted for delivery")
                            # return True
                            # delete_file_in_directory(pdf_file_name)
                        else:
                            print(f"Email not accepted. Server response: {response}")
                            # return False
                else:
                    send_mail(
                        subject=subject,
                        message=message,
                        html_message=html_message,
                        from_email=str(settings.DEFAULT_FROM_EMAIL),
                        recipient_list=recipients,
                    )
            return
        except Exception as e:
            print(f"Message of exception as {str(e)}")
            return
