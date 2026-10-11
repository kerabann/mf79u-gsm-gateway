#!/usr/bin/env python3
from cs_observation_evidence import observation_evidence
rows=['[ 100.0] MF79U_CS_CHANNEL armed seconds=180',
      '[ 105.0] MF79U_CS_CHANNEL heartbeat samples=250',
      '[ 110.0] MF79U_CS_KCONNECT tx_type=07 wire_length=2 queue_result=0',
      '[ 111.0] MF79U_CS_KCONNECT message_type=0f decoded_body_length=2',
      '[ 120.0] MF79U_CS_KCONNECT message_type=2a decoded_body_length=1348',
      '[ 125.0] MF79U_CS_CHANNEL heartbeat samples=1250']
assert observation_evidence(rows)['sampler_covered_connected_call']
assert not observation_evidence(rows+['[ 108.0] MF79U_CS_CHANNEL expired seconds=180'])['sampler_covered_connected_call']
assert not observation_evidence(rows[:-1])['sampler_covered_connected_call']
assert not observation_evidence([r for r in rows if 'samples=250' not in r])['sampler_covered_connected_call']
assert not observation_evidence([r for r in rows if 'message_type=0f' not in r])['sampler_covered_connected_call']
assert not observation_evidence(rows+['[ 115.0] MF79U_CS_CHANNEL expired seconds=180'])['sampler_covered_connected_call']
assert observation_evidence(rows)['cs_audio_verified'] is False
network_release=[r for r in rows if 'message_type=2a ' not in r]+[
 '[ 120.0] MF79U_CS_KCONNECT message_type=2d decoded_body_length=1380',
 '[ 120.1] MF79U_CS_KCONNECT tx_type=2a wire_length=2 queue_result=0']
assert observation_evidence(network_release)['network_clearing_complete']
assert observation_evidence(network_release)['clearing_evidence']=='release_complete_queued_after_network_release'
assert observation_evidence(network_release)['sampler_covered_connected_call']
failed_release=[r.replace('queue_result=0','queue_result=-1') if 'tx_type=2a' in r else r for r in network_release]
assert not observation_evidence(failed_release)['network_clearing_complete']
print('PASS sampler coverage: pre-call expiry, mid-call expiry and missing boundary heartbeats rejected')
