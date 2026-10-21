#!/usr/bin/env python3
"""Render a reviewable private HTTPS plan locally. Never applies DNS/TLS changes."""
import argparse
import ipaddress
import json
from pathlib import Path
import re


def prepare(host, listen, allowed, chain='/etc/fca/tls/fullchain.pem', key='/etc/fca/tls/privkey.pem'):
    host=host.lower()
    if (len(host)>253 or '.' not in host or not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',p) for p in host.split('.'))):
        raise ValueError('Vollständigen DNS-Namen ohne Protokoll oder Pfad angeben.')
    try: ipaddress.ip_address(host)
    except ValueError: pass
    else: raise ValueError('Google benötigt hier einen DNS-Namen, keine IP-Adresse.')
    address=ipaddress.ip_address(listen)
    if not address.is_private or address.is_unspecified or address.is_multicast or address.is_loopback:
        raise ValueError('Explizite private Serveradresse erforderlich.')
    networks=[ipaddress.ip_network(v,strict=True) for v in allowed]
    if not networks or any(not n.is_private or n.prefixlen==0 or n.is_multicast or n.is_loopback for n in networks):
        raise ValueError('Nur ausdrücklich zugelassene private LAN-/WireGuard-Netze verwenden.')
    for value in (chain,key):
        if not re.fullmatch(r'/[A-Za-z0-9_./-]+',value) or '..' in Path(value).parts:
            raise ValueError('Zertifikatpfad ist ungültig.')
    origin='https://'+host
    allow='\n'.join(' allow '+str(n)+';' for n in networks)
    binding='['+str(address)+']' if address.version==6 else str(address)
    nginx=f'''# Prepared only: requires explicit DNS/TLS/deployment approval.
limit_req_zone $binary_remote_addr zone=fca_login:1m rate=6r/m;
server {{
 listen {binding}:443 ssl;
 server_name {host};
 ssl_certificate {chain};
 ssl_certificate_key {key};
 ssl_protocols TLSv1.2 TLSv1.3;
{allow}
 deny all;
 root /var/www/fca;
 index index.html;
 server_tokens off;
 client_max_body_size 16k;
 add_header Strict-Transport-Security 'max-age=86400' always;
 add_header X-Content-Type-Options nosniff always;
 add_header Referrer-Policy no-referrer always;
 add_header X-Frame-Options DENY always;
 add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; form-action 'self'" always;
 # No authorization codes, states or provider errors in access/error logs.
 access_log off;
 error_log /dev/null crit;
 location = /api/auth/login {{
  limit_req zone=fca_login burst=4 nodelay;
  limit_req_status 429;
  proxy_pass http://127.0.0.1:8000;
  proxy_set_header Host $host;
  proxy_set_header X-Forwarded-Proto https;
  proxy_set_header X-Forwarded-For $remote_addr;
 }}
 location /api/ {{
  proxy_pass http://127.0.0.1:8000;
  proxy_set_header Host $host;
  proxy_set_header X-Forwarded-Proto https;
  proxy_set_header X-Forwarded-For $remote_addr;
 }}
 location / {{ try_files $uri $uri/ /index.html; }}
}}
'''
    plan={'status':'prepared_not_applied','origin':origin,'redirect_uri':origin+'/api/oauth/callback',
          'internal_dns':{'name':host,'address':str(address)},'public_dns':{'A_AAAA_required':False,'challenge_name':'_acme-challenge.'+host,'method':'DNS-01'},
          'certificate':{'chain':chain,'key':key,'renewal':'Administrator-managed DNS-01 renewal and tested nginx reload'},
          'allowed_networks':[str(n) for n in networks],
          'approval_required':['DNS/domain changes','certificate installation/renewal','external OAuth app registration','real cloud login']}
    return plan,nginx


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',required=True);parser.add_argument('--listen-address',required=True)
    parser.add_argument('--allow',action='append',required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--certificate-chain',default='/etc/fca/tls/fullchain.pem')
    parser.add_argument('--certificate-key',default='/etc/fca/tls/privkey.pem')
    args=parser.parse_args()
    plan,nginx=prepare(args.host,args.listen_address,args.allow,args.certificate_chain,args.certificate_key)
    args.output.mkdir(mode=0o700,parents=True,exist_ok=False)
    for name,content in [('plan.json',json.dumps(plan,indent=2)+'\n'),('nginx.conf',nginx),('origin.env','FCA_PUBLIC_ORIGIN='+plan['origin']+'\n')]:
        with (args.output/name).open('x') as handle:handle.write(content)
    print('Lokaler Prüfplan erstellt; keine DNS-, Zertifikats- oder Serveränderungen ausgeführt.')


if __name__=='__main__':main()
