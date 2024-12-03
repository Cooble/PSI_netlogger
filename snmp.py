"""
Retrieve SNMP tables and values from a device using SNMP
"""


import asyncio
from pysnmp.hlapi.v3arch.asyncio import *

# https://oid-rep.orange-labs.fr/cgi-bin/display?tree=1.3.6.1.2.1.4.21.1#focus
def inc_oid(oid):
    _oid = oid.split('.')
    lastint = int(_oid[-1])
    _oid[-1] = str(lastint + 1)
    return '.'.join(_oid)


def convertToString(val):
    if isinstance(val,IpAddress):
        return ".".join(["%d" % x for x in val.asNumbers()])
    return str(val)

def convertToInt(val):
    if isinstance(val,IpAddress):
        return int.from_bytes(val.asOctets(),"big")
    return int(val)

async def snmp_walk_async(oid= "1.3.6.1.2.1.4.21",host = "10.0.1.254",file="cdp.txt"):
    resultstr = ''
    endoid = inc_oid(oid)
    snmpengine= SnmpEngine()
    community = "public"
    routing_table = []

    while True:
        (errorIndication, 
        errorStatus, 
        errorIndex, 
        varBinds)  = await nextCmd(
                    snmpengine,
                    CommunityData(community, mpModel=0),
                    await UdpTransportTarget.create((host, 161)),
                    ContextData(),
                    ObjectType(ObjectIdentity(oid)),
                    lexicographicMode=False)

        if errorIndication:
            print(errorIndication)
            break
        elif errorStatus:
            print('%s at %s' % (errorStatus.prettyPrint(),
                                errorIndex and varBinds[int(errorIndex) - 1][0] or '?'))
            break

        else:
            #print(varBinds)
           
            #print( varBinds[0][0], " -> ", varBinds[0][1])
            varBind = varBinds[0][0]



            oid = varBind
            oid = str(oid)

            if oid >= endoid:
                break

            for varBind in varBinds:
                resultstr += ' = '.join([x.prettyPrint() for x in varBind]) + '\n'

            if file:
                with open(file, 'a', 1) as cdp_file:
                    for i in range(len(varBinds)):
                        cdp_file.write(str(varBinds[i]) + '\n')


            # Parse the SNMP response
            for varBind in varBinds:
                oid, value = varBind
                routing_table.append((str(oid), value))  # Store OID and value as a tuple

    return routing_table


async def snmp_get_async(oid= "1.3.6.1.2.1.4.21",host = "10.0.1.254",file="cdp.txt"):
    resultstr = ''
    snmpengine= SnmpEngine()
    community = "public"
    routing_table = []

    (errorIndication, 
    errorStatus, 
    errorIndex, 
    varBinds)  = await getCmd(
                snmpengine,
                CommunityData(community, mpModel=0),
                await UdpTransportTarget.create((host, 161)),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
                lexicographicMode=False,timeout=1)

    if errorIndication:
        print(errorIndication)
        
    elif errorStatus:
        print('%s at %s' % (errorStatus.prettyPrint(),
                            errorIndex and varBinds[int(errorIndex) - 1][0] or '?'))
        
    else:
        varBind = varBinds[0][0]

        oid = varBind
        oid = str(oid)

        for varBind in varBinds:
            resultstr += ' = '.join([x.prettyPrint() for x in varBind]) + '\n'

        if file:
            with open(file, 'a', 1) as cdp_file:
                for i in range(len(varBinds)):
                    cdp_file.write(str(varBinds[i]) + '\n')


        # Parse the SNMP response
        for varBind in varBinds:
            oid, value = varBind
            routing_table.append((str(oid), value))  # Store OID and value as a tuple

    return routing_table



class DictToObj:
    """
    Syntax sugar container for one entry in SNMP table
    """
    def __init__(self, dictionary):
        self.__dict__.update(dictionary)

    # operator overloading
    def __getitem__(self, name):
        if name in self.__dict__:
            return self.__dict__[name]
        if name[0]=='n' and name[1].upper() == name[1]:
            return convertToString(self.__dict__[name[1].lower() + name[2:]])
        if name[0]=='c' and name[1].upper() == name[1]:
            return convertToInt(self.__dict__[name[1].lower() + name[2:]])
    
    def __getattr__(self, name):
        if name in self.__dict__:
            return self.__dict__[name]
        if name[0]=='n' and name[1].upper() == name[1]:
            return convertToString(self.__dict__[name[1].lower() + name[2:]])
        if name[0]=='c' and name[1].upper() == name[1]:
            return convertToInt(self.__dict__[name[1].lower() + name[2:]])
        
    def __setattr__(self, name, value):
        # check if the value that we will be overwriting is IPAddress
        if isinstance(self.__dict__[name],IpAddress):
            # convert the value to IPAddress
            self.__dict__[name] = IpAddress(value)
        else:
            self.__dict__[name] = value
        
    def getString(self, name):
        return convertToString(self.__dict__[name])

def convert_to_table(entries,globalname, columnNames):
    """
    Convert a list of SNMP entries to a table format
    entries - list of tuples (oid, value)
    globalname - common prefix for all OIDs
    columnNames - map of column idx to column name
    """
    table = {}

    for oid,value in entries:
        activeName = oid.split(globalname)[1][1:]
        colIdx = activeName.split(".")[0]
        rowIdx = ".".join(activeName.split(".")[1:])
        if rowIdx not in table:
            table[rowIdx] = {}
        if colIdx in columnNames:
            name = columnNames[colIdx]
            table[rowIdx][name] = value

        
    # now convert each dic to 
    for key in table:
        table[key] = DictToObj(table[key])
    
    # convert table to list
    return [table[key] for key in table]


def mergeIntoFirst(table1,table2,key, values = None,ignoreInvalid = False):
    """
    Merge two tables into the first table
    
    table1 - list of objects
    table2 - list of objects
    key - key to match the rows
    values - whitelist of values to copy from table2 to table1
    ignoreInvalid - if True, do not add rows from table1 that do not have a match in table2
    """

    out = []
    for i in table1:
        foundJRow = False
        for j in table2:
            if i[key] == j[key]:
                foundJRow = True
                if values:
                    for k in values:
                        i.__dict__[k] = j.__dict__[k]              
                else:
                    for k in j.__dict__:
                        i.__dict__[k] = j.__dict__[k]
                out.append(i)
                break
        if not foundJRow and not ignoreInvalid:
            # add the empty values
            if values:
                for k in values:
                    i.__dict__[k] = "NaN"
            else:
                for k in j.__dict__:
                    i.__dict__[k] = "NaN"
            out.append(i)
          
    return out


def getTable(oid,host,columnNames,file=None):
    """
    Return list of entries from SNMP table
    """
    blemc =  asyncio.run(snmp_walk_async(oid=oid,host=host,file=file))
    return convert_to_table(blemc,oid,columnNames)

def getValue(oid,host):
    """
    Return single value from SNMP
    """
    return asyncio.run(snmp_get_async(oid=oid,host=host))[0][1]


def printTable(table):
    # Collect the headers and filter columns
    firstItem = next(iter(table), None)

    # If the table is empty, return
    if not firstItem:
        print("Table is empty.")
        return

    # Collect all headers from the first item
    headers = [key for key in firstItem.__dict__]

    # Compute the maximum width for each column by finding the longest string in every column
    column_widths = [len(header) for header in headers]
    for item in table:
        for i, header in enumerate(headers):
            column_widths[i] = max(column_widths[i], len(item.getString(header)))

    # Print the headers with appropriate spacing
    header_line = "  ".join(f"{(header[0].upper()+header[1:]):<{column_widths[i]}}" for i, header in enumerate(headers))
    print(header_line)

    # Print each row's values with appropriate spacing
    for item in table:
        row_line = "  ".join(f"{item.getString(header):<{column_widths[i]}}" for i, header in enumerate(headers))
        print(row_line)

