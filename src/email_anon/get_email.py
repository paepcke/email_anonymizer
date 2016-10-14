# every 5 min
# cron job
# Put a label/ archive/ 
from util import *

response = get_inbox()
student_db,student_group,student_ta = parse_student_info()
#Loop through message ID, parse the messages and extract the required info
for messagegId,data in response.iteritems():
        messageString= data['RFC822']
        msgStringParsed = email.message_from_string(messageString)
        sender =  msgStringParsed['From'].split('<')[1][:-1]

        ## if email received from student
        print sender
        if sender != HEAD_TA:
            print 'Student'
            msg = MIMEMultipart()
            msg['From'] = str(student_db[sender])
            msg['To'] = HEAD_TA
            msg['Subject'] = str(student_db[sender])+'##'+ msgStringParsed['Subject']
            body = get_body(msgStringParsed)
            msg.attach(MIMEText(body, 'plain'))
           # server2.sendmail(sender, [HEAD_TA], msg.as_string())
            ### Send this email

        # if email received from HEAD-TA
        else:
            print 'TA'
            # student_id = int(msgStringParsed['Subject'].split('##')[0])
            # msg = MIMEMultipart()
            # msg['From'] = student_ta[student_group[student_id]]  # from changed to robota or stats60ta corresponding to the email id that student sent to
            # msg['Subject'] = msgStringParsed['Subject'].split('##')[1]
            # msg['To'] = student_db.keys()[student_db.values().index(student_id)]
            # print msg.as_string()
            #server2.sendmail(sender, [msg['To']], msg.as_string())
            ### Send this email

server.close_folder()
server.logout()