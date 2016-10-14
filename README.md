# email_anonymizer
Email relay that receives from multiple aliases, encodes senders, and forwards. Same in reverse. Used for psych experiments.

- chmod +x get_email.py
- Command: './get_email.py'
- Script runs every 30 seconds (can change in line 'threading.Timer(30.0, main).start()' in get_email.py)
- Set HEAD_TA in 'util.py'
- Checks unread emails
- Only for students in the database 'official_randomization.csv'. If need to add more students, kill the script and restart.
- Shows interactions in console.
