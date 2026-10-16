*** Settings ***
Library    SSHLibrary

*** Variables ***
# The agent runs on the same node and reaches the server through this name, set in /etc/hosts
${TEST_HOST}         wazuh.ns8-ci.test
${AGENT_NAME}        robot-agent
${ADMIN_PASSWORD}    Robot.Test-2026
${AGENT_SCRIPT}      ${CURDIR}/../scripts/install-agent.sh
# The cluster admin of the CI node, set by the NS8 install
${CLUSTER_USER}      admin
${CLUSTER_PASSWORD}  Nethesis,1234
${SCREENSHOTS}       ${OUTPUT DIR}/browser/screenshot

*** Keywords ***
Use the install node
    # Commands on the node of the module: runagent, ss, the agent. The leader runs the cluster actions.
    Switch Connection    install

Use the leader
    Switch Connection    leader

Run action
    [Arguments]    ${action}    ${data}={}
    Use the leader
    ${output}  ${rc} =    Execute Command
    ...    api-cli run module/${module_id}/${action} --data '${data}'
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}  0    ${action} failed: ${output}
    ${result} =    Evaluate    json.loads('''${output}''') if '''${output}'''.strip() else {}    modules=json
    [Return]    ${result}

Run action that fails
    [Arguments]    ${action}    ${data}
    Use the leader
    ${output}  ${rc} =    Execute Command
    ...    api-cli run module/${module_id}/${action} --data '${data}'
    ...    return_rc=True
    Should Not Be Equal As Integers    ${rc}  0    ${action} did not fail: ${output}
    [Return]    ${output}

Customer of the agent should be
    [Arguments]    ${expected}
    ${result} =    Run action    list-agents
    ${groups} =    Evaluate    [a['groups'] for a in $result['agents'] if a['name'] == '${AGENT_NAME}']
    Should Be Equal    ${groups}    ${{ [['${expected}']] }}

Customer should be listed
    [Arguments]    ${name}    ${agents}
    ${result} =    Run action    list-customers
    ${found} =    Evaluate    [c['agents'] for c in $result['customers'] if c['name'] == '${name}']
    Should Be Equal    ${found}    ${{ [${agents}] }}

Customer should not be listed
    [Arguments]    ${name}
    ${result} =    Run action    list-customers
    ${names} =    Evaluate    [c['name'] for c in $result['customers']]
    Should Not Contain    ${names}    ${name}

Login to cluster-admin
    New Page    https://${NODE_ADDR}/cluster-admin/
    Fill Text    text="Username"    ${CLUSTER_USER}
    Click    button >> text="Continue"
    Fill Text    text="Password"    ${CLUSTER_PASSWORD}
    Click    button >> text="Log in"
    Wait For Elements State    css=#main-content    visible    timeout=10s

Open the module page
    [Arguments]    ${page}    ${title}
    Go To    https://${NODE_ADDR}/cluster-admin/#/apps/${module_id}?page=${page}
    Wait For Elements State    iframe >>> h2 >> text="${title}"    visible    timeout=20s
    # The page lists through a task: let it fill the table before the shot
    Sleep    5s

Agent status should be
    [Arguments]    ${expected}
    ${result} =    Run action    list-agents
    ${statuses} =    Evaluate    [a['status'] for a in $result['agents'] if a['name'] == '${AGENT_NAME}']
    Should Be Equal    ${statuses}    ${{ ['${expected}'] }}

*** Test Cases ***
Check if wazuh is installed correctly
    Use the leader
    ${output}  ${rc} =    Execute Command    add-module ${IMAGE_URL} ${INSTALL_NODE}
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}  0
    &{output} =    Evaluate    ${output}
    Set Suite Variable    ${module_id}    ${output.module_id}

Check if the secrets are not readable by other users
    Use the install node
    ${mode} =    Execute Command    stat -c %a /home/${module_id}/.config/state/secrets/indexer.env
    Should Be Equal As Strings    ${mode}    600
    ${output} =    Execute Command    runagent -m ${module_id} env
    Should Not Contain    ${output}    WAZUH_INDEXER_ADMIN_PASSWORD
    Should Not Contain    ${output}    WAZUH_MANAGER_API_PASSWORD

Check if wazuh can be configured
    Run action    configure-module
    ...    {"host":"${TEST_HOST}","admin_password":"${ADMIN_PASSWORD}","lets_encrypt":false,"ldap_domain":"","ldap_admin_group":"","index_unclassified_events":false,"export_url":"","notify_enabled":false}

Check if wazuh configuration reads back
    ${config} =    Run action    get-configuration
    Should Be Equal    ${config}[host]    ${TEST_HOST}
    Should Be Equal    ${config}[ldap_domain]    ${EMPTY}
    Should Be Equal    ${config}[notify_enabled]    ${False}
    Should Be Equal As Integers    ${config}[retention_days]    365
    Should Be Equal As Integers    ${config}[agents_enrolled]    0

Check if the three services are running
    Use the install node
    FOR    ${service}    IN    wazuh-indexer    wazuh-manager    wazuh-dashboard
        ${output}  ${rc} =    Execute Command
        ...    runagent -m ${module_id} systemctl --user is-active ${service}.service
        ...    return_rc=True
        Should Be Equal As Integers    ${rc}  0
        Should Be Equal    ${output}    active
    END

Check if the agent ports are open on the node
    Use the install node
    FOR    ${port}    IN    1514    1515    1517
        ${rc} =    Execute Command    ss -ltn | grep -q ':${port} '
        ...    return_rc=True  return_stdout=False
        Should Be Equal As Integers    ${rc}  0
    END

Check if the module timers are enabled
    Use the install node
    FOR    ${timer}    IN    send-findings-export.timer    send-findings-email.timer    provision-retention.timer
        ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user is-enabled ${timer}
        ...    return_rc=True  return_stdout=False
        Should Be Equal As Integers    ${rc}  0
    END

Check if wazuh reports its health
    ${health} =    Run action    get-health
    Should Be Equal    ${health}[indexer][status]    green

Check if the administrator can log in
    Use the install node
    ${output} =    Execute Command
    ...    runagent -m ${module_id} podman exec wazuh-indexer curl -sk -o /dev/null -w '\%{http_code}' -u 'admin:${ADMIN_PASSWORD}' https://localhost:9200/
    Should Be Equal    ${output}    200

Check if a saved setting does not restart the services
    Use the install node
    ${before} =    Execute Command    runagent -m ${module_id} podman inspect -f '{{.State.StartedAt}}' wazuh-manager
    Run action    configure-module
    ...    {"host":"${TEST_HOST}","lets_encrypt":false,"ldap_domain":"","ldap_admin_group":"","index_unclassified_events":true,"export_url":"","notify_enabled":false}
    Use the install node
    ${after} =    Execute Command    runagent -m ${module_id} podman inspect -f '{{.State.StartedAt}}' wazuh-manager
    Should Be Equal    ${before}    ${after}

Check if the log retention is set in the indexer
    Run action    configure-module
    ...    {"host":"${TEST_HOST}","lets_encrypt":false,"ldap_domain":"","ldap_admin_group":"","index_unclassified_events":false,"export_url":"","notify_enabled":false,"retention_days":400}
    ${config} =    Run action    get-configuration
    Should Be Equal As Integers    ${config}[retention_days]    400
    Use the install node
    FOR    ${policy}    IN    stream-events-policy    stream-findings-policy
        ${output} =    Execute Command
        ...    runagent -m ${module_id} podman exec wazuh-indexer curl -sk -u 'admin:${ADMIN_PASSWORD}' https://localhost:9200/_plugins/_ism/policies/${policy}
        Should Contain    ${output}    "min_rollover_age":"400d"
        # 400 days: a rollover every 33 days, so each stream keeps about 13 indices
        Should Contain    ${output}    "min_index_age":"33d"
    END

Check if an agent on the same node can enroll
    Use the install node
    Execute Command    grep -q '${TEST_HOST}' /etc/hosts || echo '127.0.0.1 ${TEST_HOST}' >> /etc/hosts
    Put File    ${AGENT_SCRIPT}    /root/install-agent.sh    mode=0700
    ${token} =    Run action    get-enrollment-token    {"max_uses":1,"description":"robot","group":"robot"}
    Should Be Equal    ${token}[address]    ${TEST_HOST}
    Use the install node
    # The token goes through a root only file, never on the command line
    Execute Command    umask 077; printf '%s' '${token}[token]' > /root/robot.token
    ${output}  ${stderr}  ${rc} =    Execute Command
    ...    bash /root/install-agent.sh --token-file /root/robot.token --name ${AGENT_NAME} --group robot
    ...    return_rc=True  return_stderr=True
    Execute Command    rm -f /root/robot.token
    Should Be Equal As Integers    ${rc}  0    ${stderr}
    Wait Until Keyword Succeeds    2 min    10 s    Agent status should be    active

Check if the host name is locked by the agent
    Use the leader
    ${output}  ${rc} =    Execute Command
    ...    api-cli run module/${module_id}/configure-module --data '{"host":"other.ns8-ci.test","lets_encrypt":false,"ldap_domain":"","ldap_admin_group":"","index_unclassified_events":false,"export_url":""}'
    ...    return_rc=True
    Should Not Be Equal As Integers    ${rc}  0
    Should Contain    ${output}    host_locked_by_agents

Check if the agent update keeps the enrollment
    ${agents} =    Run action    list-agents
    Use the install node
    ${output}  ${stderr}  ${rc} =    Execute Command
    ...    bash /root/install-agent.sh --update --version ${agents}[package_version]
    ...    return_rc=True  return_stderr=True
    Should Be Equal As Integers    ${rc}  0    ${stderr}
    Wait Until Keyword Succeeds    2 min    10 s    Agent status should be    active

Check if the certificates can be issued again
    Run action    renew-certificates
    Use the install node
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user is-active wazuh-manager.service
    ...    return_rc=True  return_stdout=False
    Should Be Equal As Integers    ${rc}  0
    # Same certificate authority: the agent reconnects without a new token
    Wait Until Keyword Succeeds    3 min    10 s    Agent status should be    active

Check if a token needs a customer
    ${output} =    Run action that fails    get-enrollment-token    {"max_uses":1}
    Should Contain    ${output}    required
    ${output} =    Run action that fails    get-enrollment-token    {"max_uses":1,"group":"default"}
    Should Contain    ${output}    group

Check if the customer has login zones
    Customer should be listed    robot    1
    Run action    set-customer    {"name":"robot","zones":["@EU","CA"],"recipients":["soc@ns8-ci.test"]}
    ${result} =    Run action    list-customers
    ${robot} =    Evaluate    [c for c in $result['customers'] if c['name'] == 'robot'][0]
    Should Be Equal    ${robot}[zones]    ${{ ['@EU', 'CA'] }}
    Should Be Equal    ${robot}[recipients]    ${{ ['soc@ns8-ci.test'] }}
    Should Contain    ${result}[countries]    FR
    Should Be Equal    ${result}[continents][EU]    Europe
    Use the install node
    ${mode} =    Execute Command    stat -c %a /home/${module_id}/.config/state/customers.json
    Should Be Equal As Strings    ${mode}    600
    # The zones reach the engine as a KVDB the login zone decoder reads
    ${output} =    Execute Command
    ...    runagent -m ${module_id} podman exec wazuh-indexer curl -sk -u 'admin:${ADMIN_PASSWORD}' -H 'Content-Type: application/json' https://localhost:9200/wazuh-threatintel-kvdbs/_search -d '{"query":{"match_phrase":{"document.metadata.title":"ns8-login-zones"}}}'
    Should Contain    ${output}    ,robot,list
    Should Contain    ${output}    ,robot,@EU

Check if the zones of a customer are checked
    Run action that fails    set-customer    {"name":"robot","zones":["XYZ"],"recipients":[]}
    Run action that fails    set-customer    {"name":"robot","zones":["@XX"],"recipients":[]}
    Run action that fails    set-customer    {"name":"robot","zones":[],"recipients":["not-an-address"]}
    ${output} =    Run action that fails    set-customer    {"name":"nobody","zones":["FR"],"recipients":[]}
    Should Contain    ${output}    customer_not_found

Check if the agent can change customer
    ${agents} =    Run action    list-agents
    ${ids} =    Evaluate    [a['id'] for a in $agents['agents'] if a['name'] == '${AGENT_NAME}']
    Set Suite Variable    ${agent_id}    ${ids}[0]
    # A customer that does not exist yet is created on the way
    Run action    set-agent-customer    {"id":"${agent_id}","customer":"robot-moved"}
    Customer of the agent should be    robot-moved
    Customer should be listed    robot-moved    1
    Customer should be listed    robot    0
    Run action that fails    set-agent-customer    {"id":"${agent_id}","customer":"default"}
    # It keeps its key: no new enrollment
    Wait Until Keyword Succeeds    2 min    10 s    Agent status should be    active

Check the pages of the module and take screenshots
    [Tags]    ui
    Import Library    Browser
    New Browser    chromium    headless=True
    New Context    ignoreHTTPSErrors=True    viewport={'width': 1440, 'height': 900}
    Login to cluster-admin
    Open the module page    status    Status
    Take Screenshot    filename=${SCREENSHOTS}/1._Status.png
    Open the module page    agents    Agents
    Wait For Elements State    iframe >>> text="${AGENT_NAME}"    visible    timeout=20s
    Get Text    iframe >>> tbody    contains    robot-moved
    Take Screenshot    filename=${SCREENSHOTS}/2._Agents.png
    # The agent menu offers the move to another customer, the modal opens empty
    Click    iframe >>> tbody tr:has(td:text-is("${AGENT_NAME}")) >> .bx--overflow-menu
    Click    iframe >>> .bx--overflow-menu-options__btn >> text="Change customer"
    Wait For Elements State    iframe >>> .bx--modal.is-visible >> text="Its customer is now robot-moved."    visible    timeout=10s
    Get Property    iframe >>> .bx--modal.is-visible input    value    ==    ${EMPTY}
    Take Screenshot    filename=${SCREENSHOTS}/3._Change_customer.png
    Click    iframe >>> .bx--modal.is-visible button >> text="Cancel"
    Click    iframe >>> text="Enrollment"
    Wait For Elements State    iframe >>> button >> text="Create a token"    visible    timeout=10s
    Take Screenshot    filename=${SCREENSHOTS}/4._Enrollment.png
    Open the module page    customers    Customers
    Wait For Elements State    iframe >>> text="Europe (continent)"    visible    timeout=20s
    Get Text    iframe >>> tbody    contains    soc@ns8-ci.test
    Take Screenshot    filename=${SCREENSHOTS}/5._Customers.png
    # The customer with zones opens with them, and the picker offers the continents first
    # Exact name: robot-moved also holds robot
    Click    iframe >>> tbody tr:has(td:text-is("robot")) >> .bx--overflow-menu
    Click    iframe >>> .bx--overflow-menu-options__btn >> text="Edit"
    Wait For Elements State    iframe >>> .bx--modal.is-visible >> text="Canada (CA)"    visible    timeout=10s
    Take Screenshot    filename=${SCREENSHOTS}/6._Edit_customer.png
    Click    iframe >>> .bx--modal.is-visible button >> text="Cancel"
    Open the module page    settings    Settings
    Take Screenshot    filename=${SCREENSHOTS}/7._Settings.png
    Close Browser

Check if a failed move leaves no customer behind
    Run action that fails    set-agent-customer    {"id":"999","customer":"robot-typo"}
    Customer should not be listed    robot-typo

Check if a customer with agents cannot be removed
    ${output} =    Run action that fails    remove-customer    {"name":"robot-moved"}
    Should Contain    ${output}    customer_has_agents
    Customer should be listed    robot-moved    1

Check if an empty customer can be removed
    Run action    set-agent-customer    {"id":"${agent_id}","customer":"robot"}
    Customer of the agent should be    robot
    Run action    remove-customer    {"name":"robot-moved"}
    Customer should not be listed    robot-moved
    ${output} =    Run action that fails    remove-customer    {"name":"robot-moved"}
    Should Contain    ${output}    customer_not_found
    # Its settings go with it, the ones of the other customer stay
    ${result} =    Run action    list-customers
    ${robot} =    Evaluate    [c for c in $result['customers'] if c['name'] == 'robot'][0]
    Should Be Equal    ${robot}[zones]    ${{ ['@EU', 'CA'] }}

Check if the agent can be revoked
    ${agents} =    Run action    list-agents
    ${ids} =    Evaluate    [a['id'] for a in $agents['agents'] if a['name'] == '${AGENT_NAME}']
    Run action    remove-agent    {"id":"${ids}[0]"}
    ${agents} =    Run action    list-agents
    ${names} =    Evaluate    [a['name'] for a in $agents['agents']]
    Should Not Contain    ${names}    ${AGENT_NAME}

Check if wazuh is removed correctly
    Use the leader
    ${rc} =    Execute Command    remove-module --no-preserve ${module_id}
    ...    return_rc=True  return_stdout=False
    Should Be Equal As Integers    ${rc}  0
    Use the install node
    ${rc} =    Execute Command    firewall-cmd --list-services | grep -q ${module_id}
    ...    return_rc=True  return_stdout=False
    Should Not Be Equal As Integers    ${rc}  0

Remove the agent from the node
    Use the install node
    Execute Command    systemctl disable --now wazuh-agent; rpm -e wazuh-agent || apt-get purge -y wazuh-agent; rm -rf /var/ossec /root/install-agent.sh
    Execute Command    sed -i '/${TEST_HOST}/d' /etc/hosts
