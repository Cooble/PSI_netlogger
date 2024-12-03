from gateway import getGateway
from snmp import * 
import os
import sys
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))


def get_interfaces(host):
    info = getTable("1.3.6.1.2.1.4.20.1",host,{"1":"ip","2":"interface","3":"mask","4":"broadcastAddr"})
    desc = getTable("1.3.6.1.2.1.2.2.1",host, {"1":"interface","2":"description"})
    mergeIntoFirst(info,desc,"interface",ignoreInvalid=True)
    return info

def get_routing_table(host):
    return getTable("1.3.6.1.2.1.4.21.1", host, {"1":"destination","2":"interface","3":"metric","7":"nextHop","8":"type","11":"mask"})

def get_id(host):
    return getValue("1.3.6.1.2.1.1.5.0", convertToString(host))


route = get_routing_table("10.0.1.254")
printTable(route)
intf  = get_interfaces("10.0.1.254")
printTable(intf)

route = mergeIntoFirst(route,intf,"interface",["description"])

printTable(route)

def fillGatewayInterface(routes):
    """
    When default gateway has not specified outgoing interface, this function will fill it in based on next hop
    """

    # sort routes by mask length
    routes.sort(key=lambda x: x.mask)
    first = routes[0]
    if first.cDestination == 0 and first.cMask == 0 and first.description == "NaN":

        # find the interface with the next hop, iterate reverse
        for route in reversed(routes):
            if route.cMask & first.cNextHop == route.cDestination:
                first.interface = route.interface
                first.description = route.description
                break
    return routes
    
printTable(fillGatewayInterface(route))
print(getValue("1.3.6.1.2.1.1.5.0", "192.168.1.1"))


def int_mask_to_cidr(int_mask):
    cidr_prefix = 0
    while int_mask:
        cidr_prefix += int_mask & 1  # Check the least significant bit
        int_mask >>= 1              # Shift right to check the next bit
    return f"{cidr_prefix}"

class Router:
    def __init__(self,ip):
        self.interfaces = get_interfaces(ip)
        self.id = get_id(ip)
        self.routingTable = get_routing_table(ip)
        self.ips = set([i.ip for i in self.interfaces])
        self.nIps = set([i.nIp for i in self.interfaces])
        self.directNets = {}
        self.directNetsInterfaces = {}

class Network:
    def __init__(self,ip,mask):
        self.ip = ip
        self.mask = mask
        self.id = ip+"/"+mask
        self.routers = {}



import ipaddress

# Map network recursively
routers = {}
nets = {}


for i in range(1,10):
    localRouter  = getGateway("eth0")
    if localRouter:
        break
if not localRouter:
    print("No gateway found")
    exit(1)
print("LocalRouter ", localRouter)

def mapNetwork(routerIp,routers,nets,depth=0):
    print("Mapping ", routerIp, "Depth ", depth)
    if depth > 5:
        return

    try:
        id = get_id(routerIp)
    except:
        # no response, skip
        return
    
    if id in routers:
        # already mapped
        return
    
    r = Router(routerIp)
    
    routers[r.id] = r
    #nextHops = set([route.nNextHop for route in r.routingTable if route.nextHop not in r.ips and route.cNextHop != 0])
    for route in r.interfaces:
        # directly connected network
        netIp = route.cIp & route.cMask # ignore what is routers ip on this net and just extract the network ip
        netIp = str(ipaddress.IPv4Address(netIp))
        net = Network(netIp,int_mask_to_cidr(route.cMask))

        if net.id not in nets:
            nets[net.id] = net
        net = nets[net.id]
        r.directNets[net.id] = net
        r.directNetsInterfaces[net.id] = route.nDescription
        net.routers[r.id] = r
    

    # routers of interest
    nextHops = set([route.nNextHop for route in r.routingTable if route.cNextHop != 0 and route.nextHop not in r.ips])
    for nextHop in nextHops:
        mapNetwork(nextHop,routers,nets,depth+1)

mapNetwork(localRouter,routers,nets)

print("Routers")
for name,router in routers.items():
    print(name)
    printTable(router.interfaces)
    printTable(router.routingTable)
    print("Ips ", router.nIps)
    print("")


# visualize
import networkx as nx
import matplotlib.pyplot as plt

def build_graph(routers, nets):
    G = nx.Graph()

    # Add Router nodes
    for router_id, router in routers.items():
        G.add_node(router_id, type='router', label=f"{router_id}")

    # Add Network nodes and edges
    for net_id, net in nets.items():
        G.add_node(net_id, type='network', label=f"{net_id}")
        for router_id, interface in net.routers.items():
            interface_label = routers[router_id].directNetsInterfaces.get(net_id, "?")
            G.add_edge(router_id, net_id, label=interface_label)  # Add edge with label

    return G


def visualize_graph(G, output_file=None):

    plt.figure(figsize=(12, 8))  # Adjust dimensions (width, height)

    # Position the nodes using a layout algorithm
    pos = nx.spring_layout(G)

    # Separate nodes by type for different coloring
    router_nodes = [node for node, data in G.nodes(data=True) if data['type'] == 'router']
    network_nodes = [node for node, data in G.nodes(data=True) if data['type'] == 'network']

    # Draw nodes
    nx.draw_networkx_nodes(G, pos, nodelist=router_nodes, node_color='skyblue', label='Routers', node_size=1500)
    nx.draw_networkx_nodes(G, pos, nodelist=network_nodes, node_color='lightgreen', label='Networks', node_size=800)

    # Draw edges
    nx.draw_networkx_edges(G, pos, edge_color='gray')

    # Draw labels for nodes
    labels = nx.get_node_attributes(G, 'label')
    nx.draw_networkx_labels(G, pos, labels, font_size=10)

    # Draw edge labels for interfaces
    edge_labels = nx.get_edge_attributes(G, 'label')
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=8)

    plt.tight_layout()
    # Display the graph
    if output_file:
        plt.savefig(output_file)  # Save to file if specified
    else:
        plt.show()  # Show on screen
# Build the graph
G = build_graph(routers, nets)

# Visualize the graph
visualize_graph(G, output_file="network_topology.png")

    




