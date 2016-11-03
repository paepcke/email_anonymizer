from util import *
import csv

dump = open('email_dump.csv', 'wb')
wr = csv.writer(dump, quoting=csv.QUOTE_ALL)
wr.writerow(['From','To','Date','Subject','Body'])
server = imaplib.IMAP4_SSL(HOST, 993)
server.login(USERNAME, PASSWORD)

def get_body(email_msg):
        '''
        Dig body out of a raw email string.
        
        :param email_msg: raw email
        :type email_msg: string
        :return just the message body
        '''
        text = ""
        if email_msg.is_multipart():
            html = None
            for payload in email_msg.get_payload():
                if payload.get_content_charset() is None:
                # We cannot know the character set, so return decoded "something"
                    text = payload.get_payload(decode=True)
                    if '________________________________' in text: text = text.split('________________________________')[0]
                    continue
                charset = payload.get_content_charset()
                if payload.get_content_maintype() == 'text':
                    text = unicode(payload.get_payload(decode=True), str(charset), "ignore").encode('utf8', 'replace')
                
            if text is not None:
              if '________________________________' in text: text = text.split('________________________________')[0]
              return text.strip() 

        else:
            if email_msg.get_content_charset() is not None:
              text = unicode(email_msg.get_payload(decode=True), email_msg.get_content_charset(), 'ignore').encode('utf8', 'replace')
            else: text = email_msg.get_payload(decode=True)
            if '________________________________' in text: text = text.split('________________________________')[0]
            return text.strip()

def get_body2( email_msg):
        '''
        Dig body out of a raw email string.
        
        :param email_msg: raw email
        :type email_msg: string
        :return just the message body
        '''
        
        if email_msg.is_multipart():
            # print email_msg.get_payload(0)
            # return email_msg.get_payload(0)
            for payload in email_msg.get_payload():
                #print payload.get_payload()
                if payload.get_content_maintype() == 'text':
                    return payload.get_payload()
        else: return email_msg.get_payload()
def get_inbox():
    select_info = server.select('INBOX',readonly=True)
    status, response = server.search(None, 'All')
    msg_nums = response[0].split()
    da = []
    for e_id in msg_nums:
        _, response = server.fetch(e_id,'(RFC822)')
        da.append(response[0][1])
    return da


def parse_emails(response):
    for data in response:
                msgStringParsed = email.message_from_string(data)
                frm =  msgStringParsed['From']
                if '<' in frm: frm =  msgStringParsed['From'].split('<')[1][:-1]
                to =  msgStringParsed['To'].split(' ')[0]
                subject = msgStringParsed['Subject']
                body = get_body2(msgStringParsed)
                date= msgStringParsed['Date']
                msg = MIMEMultipart("alternative")
                msg['From'] = frm
                msg['Subject'] = subject
                msg['To'] = ''
                print MIMEText(body.encode('utf-8'), 'plain','utf-8')
                msg.attach(MIMEText(body.encode('utf-8'), 'plain','utf-8'))
                #print msg.as_string().encode('ascii')
                #wr.writerow([frm,to,date,subject,body])

data = get_inbox()
parse_emails(data)
