*** Settings ***
Library    SSHLibrary

*** Variables ***
# The agent runs on the same node and reaches the server through this name, set in /etc/hosts
${TEST_HOST}         wazuh.ns8-ci.test
${AGENT_NAME}        robot-agent
${ADMIN_PASSWORD}    Robot.Test-2026
${AGENT_SCRIPT}      ${CURDIR}/../scripts/install-agent.sh

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

Check if an agent on the same node can enroll
    Use the install node
    Execute Command    grep -q '${TEST_HOST}' /etc/hosts || echo '127.0.0.1 ${TEST_HOST}' >> /etc/hosts
    Put File    ${AGENT_SCRIPT}    /root/install-agent.sh    mode=0700
    ${token} =    Run action    get-enrollment-token    {"max_uses":1,"description":"robot"}
    Should Be Equal    ${token}[address]    ${TEST_HOST}
    Use the install node
    # The token goes through a root only file, never on the command line
    Execute Command    umask 077; printf '%s' '${token}[token]' > /root/robot.token
    ${output}  ${stderr}  ${rc} =    Execute Command
    ...    bash /root/install-agent.sh --token-file /root/robot.token --name ${AGENT_NAME}
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
