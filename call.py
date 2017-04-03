from twilio.rest import TwilioRestClient

from settings import TWILIO_ACCOUNT_SID, TWILIO_PHONE_NUMBER, TWILIO_TOKEN

# URL location of TwiML instructions for how to handle the phone call
TWIML_INSTRUCTIONS_URL = \
  'http://static.fullstackpython.com/phone-calls-python.xml'

client = TwilioRestClient(TWILIO_ACCOUNT_SID, TWILIO_TOKEN)


def dial_numbers(numbers_list):
    '''Dials one or more phone numbers from a Twilio phone number.'''
    for number in numbers_list:
        print('Dialing ' + number)
        # set the method to 'GET' from default POST because Amazon S3 only
        # serves GET requests on files. Typically POST would be used for apps
        client.calls.create(to=number, from_=TWILIO_PHONE_NUMBER,
                            url=TWIML_INSTRUCTIONS_URL, method='GET')
