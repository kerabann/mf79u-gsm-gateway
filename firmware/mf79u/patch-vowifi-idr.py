from pathlib import Path
root=Path('work/zte/voice/vowifi/strongswan-6.1.0')
p=root/'src/libcharon/sa/ikev2/tasks/ike_auth.c';s=p.read_text();old='''id_payload = id_payload_create_from_identification(
															PLV2_ID_RESPONDER, idr);'''
if 'mf79u_apn' not in s:
 assert old in s
 new='''/* SWu IDr requests the APN; the configured remote identity still
                 * constrains the authenticated ePDG returned in its IDr. */
                identification_t *apn = NULL;
                char *apn_name = lib->settings->get_str(lib->settings,
                    "%s.mf79u_apn", NULL, lib->ns);
                if (apn_name && !strcmp(apn_name, "ims") &&
                    !strcmp(this->peer_cfg->get_name(this->peer_cfg), "vowifi"))
                {
                    apn = identification_create_from_string(apn_name);
                }
                id_payload = id_payload_create_from_identification(
                    PLV2_ID_RESPONDER, apn ? apn : idr);
                DESTROY_IF(apn);'''
 s=s.replace(old,new,1);p.write_text(s)

# SWu requests a fresh virtual address on full reauthentication. Keep generic
# IKE behavior unchanged; the operator may reject a retained IMS VIP request.
import tarfile
p=root/'src/libcharon/sa/ike_sa.c'
with tarfile.open(str(root)+'.tar.bz2') as archive:
 s=archive.extractfile('strongswan-6.1.0/src/libcharon/sa/ike_sa.c').read().decode()
needle='new->add_virtual_ip(new, TRUE, host);'
assert s.count(needle)==1
s=s.replace(needle, 'if (!streq(this->peer_cfg->get_name(this->peer_cfg), "vowifi"))\n\t\t{\n\t\t\t'+needle+'\n\t\t}')
p.write_text(s)
