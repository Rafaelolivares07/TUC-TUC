import tinytuya, json

c = tinytuya.Cloud(
    apiRegion='us',
    apiKey='9p9nr8s3nv8sdth78v5u',
    apiSecret='644b3e3813c640bfb3aa3efe95437683'
)

device_id = 'ebe4f458f0427bc8a08lgy'

# Prender el enchufe
r = c.cloudrequest(
    f'/v1.0/iot-03/devices/{device_id}/commands',
    action='POST',
    post={'commands': [{'code': 'switch_1', 'value': True}]}
)
print(json.dumps(r, indent=2))
