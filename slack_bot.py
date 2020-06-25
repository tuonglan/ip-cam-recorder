import requests, json

class SlackBot:
    def __init__(self, token, channel, notifee):
        self._token = token
        self._channel = channel
        self._notifee = notifee

    def post_message(self, title, text, color='#7CD197'):
        headers = {
            'Authorization': "Bearer %s" % self._token,
            'Content-type': 'application/json'
            }
        payload = {
            'channel': self._channel,
            'text': title,
            'attachments': [{'text': text, 'color': color}]
            }

        rs = requests.post('https://slack.com/api/chat.postMessage', headers=headers, data=json.dumps(payload))
        data = rs.json()
        if not data['ok']:
            raise Exception(data['error'])
        else:
            return rs.text

    def post_info(self, title, text):
        return self.post_message(title, text)

    def post_warning(self, title, text):
        return self.post_message(title, text, '#EBB424')

    def post_alert(self, title, text):
        new_title = "%s <@%s>" % (title, self._notifee) if self._notifee else title
        return self.post_message(new_title, text, '#D40E0D')

