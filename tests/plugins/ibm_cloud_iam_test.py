import pytest
import responses

from detect_secrets.constants import VerifiedResult
from detect_secrets.plugins.ibm_cloud_iam import IbmCloudIamDetector

CLOUD_IAM_KEY = 'ukYEEX38RiGgq1BPf2m-nIeTM_lEGizKKn49RRoC_6fn'
CLOUD_IAM_KEY_BYTES = b'ukYEEX38RiGgq1BPf2m-nIeTM_lEGizKKn49RRoC_6fn'
LOW_ENTROPY_KEY = 'abcd1234abcd1234abcd1234ABCD1234ABCD1234--__'
LOW_ENTROPY_KEY_BYTES = b'abcd1234abcd1234abcd1234ABCD1234ABCD1234--__'


class TestIBMCloudIamDetector:

    @pytest.mark.parametrize(
        'payload, should_flag',
        [
            ('ibm-cloud_api_key: {cloud_iam_key}'.format(cloud_iam_key=CLOUD_IAM_KEY), True),
            ('ibm_cloud_iam-key : {cloud_iam_key}'.format(cloud_iam_key=CLOUD_IAM_KEY), True),
            ('IBM-API-KEY : "{cloud_iam_key}"'.format(cloud_iam_key=CLOUD_IAM_KEY), True),
            ('"iam_api_key" : "{cloud_iam_key}"'.format(cloud_iam_key=CLOUD_IAM_KEY), True),
            ('cloud-api-key: "{cloud_iam_key}"'.format(cloud_iam_key=CLOUD_IAM_KEY), True),
            ('"iam-password": "{cloud_iam_key}"'.format(cloud_iam_key=CLOUD_IAM_KEY), True),
            ('CLOUD_IAM_API_KEY:"{cloud_iam_key}"'.format(cloud_iam_key=CLOUD_IAM_KEY), True),
            ('ibm-cloud-key:{cloud_iam_key}'.format(cloud_iam_key=CLOUD_IAM_KEY), True),
            ('ibm_key:"{cloud_iam_key}"'.format(cloud_iam_key=CLOUD_IAM_KEY), True),
            (
                '"ibm_cloud_iam_api_key":"{cloud_iam_key}"'.format(
                    cloud_iam_key=CLOUD_IAM_KEY,
                ), True,
            ),
            ('ibm_cloud_iamapikey= {cloud_iam_key}'.format(cloud_iam_key=CLOUD_IAM_KEY), True),
            ('ibm_cloud_api_key= "{cloud_iam_key}"'.format(cloud_iam_key=CLOUD_IAM_KEY), True),
            ('IBMCLOUDIAMAPIKEY={cloud_iam_key}'.format(cloud_iam_key=CLOUD_IAM_KEY), True),
            ('cloud_iam_api_key="{cloud_iam_key}"'.format(cloud_iam_key=CLOUD_IAM_KEY), True),
            ('ibm_api_key := {cloud_iam_key}'.format(cloud_iam_key=CLOUD_IAM_KEY), True),
            ('"ibm-iam_key" := "{cloud_iam_key}"'.format(cloud_iam_key=CLOUD_IAM_KEY), True),
            (
                '"ibm_cloud_iam_api_key":"{cloud_iam_key}"'.format(
                    cloud_iam_key=CLOUD_IAM_KEY,
                ), True,
            ),
            ('ibm-cloud_api_key:={cloud_iam_key}'.format(cloud_iam_key=CLOUD_IAM_KEY), True),
            ('"cloud_iam_api_key":="{cloud_iam_key}"'.format(cloud_iam_key=CLOUD_IAM_KEY), True),
            ('ibm_iam_key:= "{cloud_iam_key}"'.format(cloud_iam_key=CLOUD_IAM_KEY), True),
            ('ibm_iam_key:= "{cloud_iam_key}extra"'.format(cloud_iam_key=CLOUD_IAM_KEY), False),
            ('ibm_api_key:="{cloud_iam_key}"'.format(cloud_iam_key=CLOUD_IAM_KEY), True),
            ('ibm_platform_key={cloud_iam_key}'.format(cloud_iam_key=CLOUD_IAM_KEY), True),
            ('ibm_password = "{cloud_iam_key}"'.format(cloud_iam_key=CLOUD_IAM_KEY), True),
            ('ibm-cloud-pwd = {cloud_iam_key}'.format(cloud_iam_key=CLOUD_IAM_KEY), True),
            ('ibm-cloud-pwd = {cloud_iam_key}extra'.format(cloud_iam_key=CLOUD_IAM_KEY), False),
            ('ibm-cloud-pwd = shorter-version', False),
            ('apikey:{cloud_iam_key}'.format(cloud_iam_key=CLOUD_IAM_KEY), True),
            ('iam_api_key="%s" % IBM_IAM_API_KEY_ENV', False),
            ('CLOUD_APIKEY: "insert_key_here"', False),
            ('cloud-iam-key:=afakekey', False),
            ('fake-cloud-iam-key= "not_long_enough"', False),
            ('ibm-cloud_api_key: {cloud_iam_key}'.format(cloud_iam_key=LOW_ENTROPY_KEY), False),
            ('ibm_cloud_iam-key : {cloud_iam_key}'.format(cloud_iam_key=LOW_ENTROPY_KEY), False),
            ('IBM-API-KEY : "{cloud_iam_key}"'.format(cloud_iam_key=LOW_ENTROPY_KEY), False),
            ('"iam_api_key" : "{cloud_iam_key}"'.format(cloud_iam_key=LOW_ENTROPY_KEY), False),
            ('cloud-api-key: "{cloud_iam_key}"'.format(cloud_iam_key=LOW_ENTROPY_KEY), False),
            ('"iam-password": "{cloud_iam_key}"'.format(cloud_iam_key=LOW_ENTROPY_KEY), False),
            ('CLOUD_IAM_API_KEY:"{cloud_iam_key}"'.format(cloud_iam_key=LOW_ENTROPY_KEY), False),
            ('ibm-cloud-key:{cloud_iam_key}'.format(cloud_iam_key=LOW_ENTROPY_KEY), False),
            ('ibm_key:"{cloud_iam_key}"'.format(cloud_iam_key=LOW_ENTROPY_KEY), False),
            (
                '"ibm_cloud_iam_api_key":"{cloud_iam_key}"'.format(
                    cloud_iam_key=LOW_ENTROPY_KEY,
                ), False,
            ),
            ('ibm_cloud_iamapikey= {cloud_iam_key}'.format(cloud_iam_key=LOW_ENTROPY_KEY), False),
            ('ibm_cloud_api_key= "{cloud_iam_key}"'.format(cloud_iam_key=LOW_ENTROPY_KEY), False),
            ('IBMCLOUDIAMAPIKEY={cloud_iam_key}'.format(cloud_iam_key=LOW_ENTROPY_KEY), False),
            ('cloud_iam_api_key="{cloud_iam_key}"'.format(cloud_iam_key=LOW_ENTROPY_KEY), False),
            ('ibm_api_key := {cloud_iam_key}'.format(cloud_iam_key=LOW_ENTROPY_KEY), False),
            ('"ibm-iam_key" := "{cloud_iam_key}"'.format(cloud_iam_key=LOW_ENTROPY_KEY), False),
            (
                '"ibm_cloud_iam_api_key":= "{cloud_iam_key}"'.format(
                    cloud_iam_key=LOW_ENTROPY_KEY,
                ), False,
            ),
            ('ibm-cloud_api_key:={cloud_iam_key}'.format(cloud_iam_key=LOW_ENTROPY_KEY), False),
            ('"cloud_iam_api_key":="{cloud_iam_key}"'.format(cloud_iam_key=LOW_ENTROPY_KEY), False),
            ('ibm_iam_key:= "{cloud_iam_key}"'.format(cloud_iam_key=LOW_ENTROPY_KEY), False),
            ('ibm_iam_key:= "{cloud_iam_key}extra"'.format(cloud_iam_key=LOW_ENTROPY_KEY), False),
            ('ibm_api_key:="{cloud_iam_key}"'.format(cloud_iam_key=LOW_ENTROPY_KEY), False),
            ('ibm_password = "{cloud_iam_key}"'.format(cloud_iam_key=LOW_ENTROPY_KEY), False),
            ('ibm-cloud-pwd = {cloud_iam_key}'.format(cloud_iam_key=LOW_ENTROPY_KEY), False),
            ('ibm-cloud-pwd = {cloud_iam_key}extra'.format(cloud_iam_key=LOW_ENTROPY_KEY), False),
            ('ibm-cloud-pwd = shorter-version', False),
            ('apikey:{cloud_iam_key}'.format(cloud_iam_key=LOW_ENTROPY_KEY), False),
        ],
    )
    def test_analyze_string_content(self, payload, should_flag):
        logic = IbmCloudIamDetector()

        output = logic.analyze_line(filename='mock_filename', line=payload)
        assert len(output) == (1 if should_flag else 0)
        if should_flag:
            assert list(output)[0].secret_value == CLOUD_IAM_KEY

    @responses.activate
    def test_verify_invalid_secret(self):
        responses.add(
            responses.POST, 'https://iam.cloud.ibm.com/identity/token', status=400,
        )

        assert IbmCloudIamDetector().verify(CLOUD_IAM_KEY) == VerifiedResult.VERIFIED_FALSE

    @responses.activate
    def test_verify_valid_secret(self):
        responses.add(
            responses.POST, 'https://iam.cloud.ibm.com/identity/token', status=200,
        )

        IbmCloudIamDetector().verify(CLOUD_IAM_KEY) == VerifiedResult.VERIFIED_TRUE

    @responses.activate
    def test_verify_invalid_secret_bytes(self):
        responses.add(
            responses.POST, 'https://iam.cloud.ibm.com/identity/token', status=400,
        )

        assert IbmCloudIamDetector().verify(CLOUD_IAM_KEY_BYTES) == VerifiedResult.VERIFIED_FALSE

    @responses.activate
    def test_verify_valid_secret_byes(self):
        responses.add(
            responses.POST, 'https://iam.cloud.ibm.com/identity/token', status=200,
        )

        IbmCloudIamDetector().verify(CLOUD_IAM_KEY_BYTES) == VerifiedResult.VERIFIED_TRUE
