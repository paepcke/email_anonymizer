from util import *

unread_msgs,response = get_inbox(server1,server2)
success=-1
if response: success = run_script(unread_msgs,response)

if success:
    for eid in unread_msgs:
        server1.store(eid, '+FLAGS', '\Seen')
else:
    for eid in unread_msgs:
        server1.store(eid, '+FLAGS', '\UnSeen')

server1.close()
server1.logout()