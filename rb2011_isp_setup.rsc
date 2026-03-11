# MikroTik RB2011 - ISP Setup v7 (fixed)
# Winbox: Files -> drag file -> /import rb2011_isp_setup.rsc
:log info "ISP Setup v7 Start"
:put "=== ISP Setup Start ==="

# 1 IDENTITY
/system identity set name=ISP-RB2011
/system clock set time-zone-name=Africa/Nairobi
:put ">>> 1 done"

# 2 PASSWORD
/user set admin password=hood
:put ">>> 2 done"

# 3 BRIDGES
:do { /interface bridge add name=bridge-pppoe } on-error={}
:do { /interface bridge add name=bridge-hotspot } on-error={}
:put ">>> 3 done"

# 4 BRIDGE PORTS
:do { /interface bridge port add bridge=bridge-pppoe interface=ether2 } on-error={}
:do { /interface bridge port add bridge=bridge-pppoe interface=ether3 } on-error={}
:do { /interface bridge port add bridge=bridge-pppoe interface=ether4 } on-error={}
:do { /interface bridge port add bridge=bridge-pppoe interface=ether5 } on-error={}
:do { /interface bridge port add bridge=bridge-pppoe interface=ether6 } on-error={}
:do { /interface bridge port add bridge=bridge-hotspot interface=ether8 } on-error={}
:do { /interface bridge port add bridge=bridge-hotspot interface=ether9 } on-error={}
:do { /interface bridge port add bridge=bridge-hotspot interface=ether10 } on-error={}
:put ">>> 4 done"

# 5 IP ADDRESSES
:do { /ip address add address=192.168.88.1/24 interface=ether7 } on-error={}
:do { /ip address add address=192.168.55.1/24 interface=bridge-pppoe } on-error={}
:do { /ip address add address=192.168.99.1/24 interface=bridge-hotspot } on-error={}
:put ">>> 5 done"

# 6 WAN DHCP CLIENT
:do { /ip dhcp-client add interface=ether1 disabled=no add-default-route=yes } on-error={}
:put ">>> 6 done"

# 7 IP POOLS
:do { /ip pool add name=pppoe-pool ranges=192.168.55.2-192.168.55.254 } on-error={}
:do { /ip pool add name=hotspot-pool ranges=192.168.99.2-192.168.99.200 } on-error={}
:do { /ip pool add name=admin-pool ranges=192.168.88.10-192.168.88.100 } on-error={}
:put ">>> 7 done"

# 8 DNS
/ip dns set servers=8.8.8.8,8.8.4.4 allow-remote-requests=yes
:put ">>> 8 done"

# 9 DHCP SERVERS
:do { /ip dhcp-server network add address=192.168.88.0/24 gateway=192.168.88.1 } on-error={}
:do { /ip dhcp-server add name=dhcp-admin interface=ether7 address-pool=admin-pool disabled=no } on-error={}
:do { /ip dhcp-server network add address=192.168.99.0/24 gateway=192.168.99.1 } on-error={}
:do { /ip dhcp-server add name=dhcp-hotspot interface=bridge-hotspot address-pool=hotspot-pool disabled=no } on-error={}
:put ">>> 9 done"

# 10 PPPoE PROFILES
:do { /ppp profile add name=plan-500  local-address=192.168.55.1 remote-address=pppoe-pool rate-limit=5M/5M   only-one=yes } on-error={}
:do { /ppp profile add name=plan-700  local-address=192.168.55.1 remote-address=pppoe-pool rate-limit=5M/5M   only-one=no  } on-error={}
:do { /ppp profile add name=plan-1000 local-address=192.168.55.1 remote-address=pppoe-pool rate-limit=7M/7M   only-one=no  } on-error={}
:do { /ppp profile add name=plan-1300 local-address=192.168.55.1 remote-address=pppoe-pool rate-limit=10M/10M only-one=no  } on-error={}
:do { /ppp profile add name=plan-grace   local-address=192.168.55.1 remote-address=pppoe-pool rate-limit=1M/512k   only-one=no } on-error={}
:do { /ppp profile add name=plan-captive local-address=192.168.55.1 remote-address=pppoe-pool rate-limit=256k/128k only-one=no } on-error={}
:put ">>> 10 done"

# 11 PPPoE SERVER
# FIX: consolidated add+params on one line; quoted name to avoid parser ambiguity
#      with double-level path /interface pppoe-server server inside :do {}
:do { /interface pppoe-server server add name="pppoe-isp" interface=bridge-pppoe service-name=ISP default-profile=plan-500 max-mtu=1480 max-mru=1480 keepalive-timeout=60 disabled=no } on-error={}
:put ">>> 11 done"

# 12 HOTSPOT USER PROFILES
:do { /ip hotspot user profile add name=hs-3min   rate-limit=2M/2M   session-timeout=3m  shared-users=1 } on-error={}
:do { /ip hotspot user profile add name=hs-2hr    rate-limit=4M/4M   session-timeout=2h  shared-users=1 } on-error={}
:do { /ip hotspot user profile add name=hs-4hr    rate-limit=4M/4M   session-timeout=4h  shared-users=1 } on-error={}
:do { /ip hotspot user profile add name=hs-6hr    rate-limit=5M/5M   session-timeout=6h  shared-users=1 } on-error={}
:do { /ip hotspot user profile add name=hs-daily  rate-limit=5M/5M   session-timeout=1d  shared-users=2 } on-error={}
:do { /ip hotspot user profile add name=hs-2day   rate-limit=5M/5M   session-timeout=2d  shared-users=2 } on-error={}
:do { /ip hotspot user profile add name=hs-weekly rate-limit=7M/7M   session-timeout=7d  shared-users=3 } on-error={}
:do { /ip hotspot user profile add name=hs-monthly rate-limit=10M/10M session-timeout=30d shared-users=5 } on-error={}
:put ">>> 12 done"

# 13 HOTSPOT SERVER
:do { /ip hotspot profile add name=hsprof-main hotspot-address=192.168.99.1 html-directory=hotspot login-by=http-chap } on-error={}
:do { /ip hotspot add name=hotspot-main interface=bridge-hotspot profile=hsprof-main address-pool=hotspot-pool disabled=no } on-error={}
:put ">>> 13 done"

# 14 NAT
:do { /ip firewall nat add chain=srcnat action=masquerade src-address=192.168.55.0/24 out-interface=ether1 comment=PPPoE-NAT } on-error={}
:do { /ip firewall nat add chain=srcnat action=masquerade src-address=192.168.99.0/24 out-interface=ether1 comment=Hotspot-NAT } on-error={}
:do { /ip firewall nat add chain=srcnat action=masquerade src-address=192.168.88.0/24 out-interface=ether1 comment=Admin-NAT } on-error={}
:do { /ip firewall nat add chain=dstnat protocol=tcp action=redirect in-interface=ether1 dst-port=28728 to-ports=8728 comment=WAN-API } on-error={}
:put ">>> 14 done"

# 15 FIREWALL
:do { /ip firewall filter add chain=input  protocol=tcp action=accept in-interface=ether1 dst-port=28728 comment=API-IN    } on-error={}
:do { /ip firewall filter add chain=input  protocol=tcp action=drop   in-interface=ether1 dst-port=8728  comment=API-BLOCK } on-error={}
:do { /ip firewall filter add chain=input  action=accept src-address=192.168.88.0/24 comment=ADMIN-LAN } on-error={}
:do { /ip firewall filter add chain=forward action=accept connection-state=established comment=ESTAB } on-error={}
:put ">>> 15 done"

# 16 SERVICES
/ip service set api     disabled=no port=8728
/ip service set api-ssl disabled=no port=8729
/ip service set winbox  disabled=no port=8291
/ip service set ssh     disabled=no port=22
:do { /ip service set telnet disabled=yes } on-error={}
:do { /ip service set ftp    disabled=yes } on-error={}
:put ">>> 16 done"

# 17 IP CLOUD
/ip cloud set ddns-enabled=yes update-time=yes
:delay 5s
:local cloudHost [/ip cloud get dns-name]
:log info ("MIKROTIK_HOST=" . $cloudHost)
:put ("MIKROTIK_HOST=" . $cloudHost)
:put "MIKROTIK_PORT=28728"
:put "MIKROTIK_USER=admin"
:put "MIKROTIK_PASSWORD=hood"
:put ">>> 17 done"

# 18 LOGGING
:do { /system logging add topics=pppoe    action=memory } on-error={}
:do { /system logging add topics=hotspot  action=memory } on-error={}
:do { /system logging add topics=account  action=memory } on-error={}
:put ">>> 18 done"

:log info "ISP Setup v7 Complete"
:put "================================"
:put "  RB2011 ISP Setup Complete!"
:put "  ether1    = WAN (DHCP)"
:put "  ether2-6  = PPPoE  192.168.55.x"
:put "  ether7    = Admin  192.168.88.1"
:put "  ether8-10 = Hotspot 192.168.99.1"
:put "================================"
