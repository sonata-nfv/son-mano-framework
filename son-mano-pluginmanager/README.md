Plugin manager: SONATA MANO framework component that is responsible to manage MANO plugins connected to the broker.

## Install

* `python setup.py develop`

## Management with CLI tool: `son-pm-cli`

* More details
    * `son-pm-cli -h`
* List all active plugins
    * `son-pm-cli list`
* Print info about specific plugin
    * `son-pm-cli info -u <uuid_of_plugin>`
* Remove (stop+disconnect) specific plugin
    * `son-pm-cli remove -u <uuid_of_plugin>`
* Trigger lifecycle change of a specific plugin
    * `son-pm-cli lifecycle-pause -u <uuid_of_plugin>`
    * `son-pm-cli lifecycle-start -u <uuid_of_plugin>` (automatically done after registration)


## Management with REST interface

Exposed on port <strong>8001</strong>.


<table>
<tr>
<th>Endpoint:</th>
<th>Method:</th>
<th>Body:</th>
<th>Response:</th>
<th>Description:</th>
</tr>

<tr>
<td>/api/plugins</td>
<td>GET</td>
<td>-</td>
<td>["uuid1", "uuid2"]</td>
<td>Receive a list containing UUIDs of all registered plugins in the system.</td>
</tr>

<tr>
<td>/api/plugins/:uuid</td>
<td>GET</td>
<td>-</td>
<td>{dict with status info}</td>
<td>Receive status information of the given plugin.</td>
</tr>

<tr>
<td>/api/plugins/:uuid</td>
<td>DELETE</td>
<td>-</td>
<td>-</td>
<td>Remotely shutdown a plugin.</td>
</tr>

<tr>
<td>/api/plugins/:uuid/lifecycle</td>
<td>PUT</td>
<td>{"target_state": "pause|start"}</td>
<td>-</td>
<td>Manipulate the lifecycle state of a plugin.</td>
</tr>

</table>