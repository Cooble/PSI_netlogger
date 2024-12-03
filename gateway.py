"""
Get the gateway IP address of the network by asking DHCP server using DIY discovery packet
Does not require device to be allocated an IP address

Note: When running in sim, the responses are way too fast
- listening for the reply must be started before sending the request
- therefore multithreaded
"""

from scapy.all import *

import threading
import time


conf.iface = "eth0"


# Function to handle sniffing in a separate thread
def sniff_thread(sniff_filter, sniff_count, sniff_timeout, result_list):
    # Capture the packets
    sniff(filter=sniff_filter, prn=lambda x: result_list.append(x), count=sniff_count, timeout=sniff_timeout)

# Threaded version of srp
def srp_threading(packet, timeout=1, verbose=True, filter=None, count=1,protoc=None):
    # List to store sniffed packets
    result_list = []

    # Start sniffing in a separate thread
    sniff_thread_instance = threading.Thread(target=sniff_thread, args=(filter, count, timeout, result_list))
    sniff_thread_instance.start()

    #time.sleep(0.001)
    # Send the packet(s)
    sendp(packet,verbose=verbose)

    # Wait for the sniffing thread to complete
    sniff_thread_instance.join()

    # Return the first captured packet, if any
    newlist = []
    if protoc is not None:
        for i in result_list:
            if protoc in i:
                newlist.append(i)
        return newlist
    
    return result_list
    


def goption(name,options):
    for tup in options:
        if type(tup) is tuple:
            if tup[0] == name:
                return tup[1]



def getGateway(iface="eth0"):
    """
    Get the gateway IP address of the network by asking DHCP server using DIY discovery packet
    """
    
    conf.iface = iface
    mac = get_if_hwaddr(iface)

    # DHCP Discover
    discover = Ether(dst='ff:ff:ff:ff:ff:ff', type=0x0800) 
    discover /= IP(src='0.0.0.0', dst='255.255.255.255') 
    discover /= UDP(dport=67,sport=68) 
    discover /= BOOTP(op=1, chaddr=mac,xid=0x1001) 
    discover /= DHCP(options=[('message-type','discover'), ('end')])

    #o = srp(discover,nofilter=1,timeout=2)
    o = srp_threading(discover,iface=conf.iface, count=10,protoc=DHCP)

    for i in o:
        if goption("router", i[DHCP].options) is not None:
            print("Got reply ")
            print(goption("router", i[DHCP].options))
            #print(goption("name_server", i[DHCP].options))
            #print(goption("subnet_mask", i[DHCP].options))
            return goption("router", i[DHCP].options)
        

#router = getGateway()


