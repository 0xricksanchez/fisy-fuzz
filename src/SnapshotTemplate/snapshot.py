xml_head_name = """<domainsnapshot> <name>{}</name>
        <state>running</state> <memory snapshot='internal'/>
        <disks><disk name='hda' snapshot='internal'/></disks>"""

xml_head = """<domainsnapshot>
        <state>running</state> <memory snapshot='internal'/>
        <disks><disk name='hda' snapshot='internal'/></disks>"""

xml_tail = "</domainsnapshot>"
