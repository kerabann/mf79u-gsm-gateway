"""Derive CS call/sampler coverage from monotonic kernel timestamps only."""
import re

def observation_evidence(rows):
 def matching(fragment):
  return [(float(m.group(1)),r) for r in rows if fragment in r
          for m in [re.search(r'\[\s*([\d.]+)\]',r)] if m]
 def first(fragment):
  return next((t for t,_ in matching(fragment)),None)
 connect=first('tx_type=07 ');ack=first('message_type=0f ')
 release=first('message_type=2a ');release_source='received_release_complete' if release is not None else None
 network_release=first('message_type=2d ')
 if release is None and network_release is not None:
  release=next((t for t,row in matching('tx_type=2a ') if t>=network_release and 'queue_result=0' in row),None)
  if release is not None:release_source='release_complete_queued_after_network_release'
 armed=first('MF79U_CS_CHANNEL armed ');expiry=first('MF79U_CS_CHANNEL expired ')
 heartbeats=matching('MF79U_CS_CHANNEL heartbeat ')
 covered=bool(ack is not None and release is not None and armed is not None and
              armed<=ack and (expiry is None or expiry>=release) and
              any(t<=ack for t,_ in heartbeats) and any(t>=release for t,_ in heartbeats))
 return {'connect_enqueue_result':0 if any('queue_result=0' in r for _,r in matching('tx_type=07 ')) else None,
         'connect_ack_observed':ack is not None,'network_clearing_complete':release is not None,
         'clearing_evidence':release_source,'network_release_observed':network_release is not None,
         'connect_enqueued_uptime':connect,'connect_ack_uptime':ack,'release_complete_uptime':release,
         'sampler_armed_uptime':armed,'sampler_expired_uptime':expiry,
         'sampler_covered_connected_call':covered,
         'connected_channel_activity_result':'metadata_observation_covered' if covered else 'inconclusive_sampler_coverage',
         'cs_audio_verified':False}
