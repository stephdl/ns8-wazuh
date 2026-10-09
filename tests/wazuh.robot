*** Settings ***
Library    SSHLibrary

*** Variables ***
# Any resolvable-looking name: the schema demands a dot, nothing resolves it.
${TEST_HOST}    wazuh.ns8-ci.test

*** Test Cases ***
Check if wazuh is installed correctly
    ${output}  ${rc} =    Execute Command    add-module ${IMAGE_URL} 1
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}  0
    &{output} =    Evaluate    ${output}
    Set Suite Variable    ${module_id}    ${output.module_id}

Check if wazuh can be configured
    ${rc} =    Execute Command
    ...    api-cli run module/${module_id}/configure-module --data '{"host":"${TEST_HOST}","lets_encrypt":false,"ldap_domain":"","ldap_admin_group":"","index_unclassified_events":false,"export_url":""}'
    ...    return_rc=True  return_stdout=False
    Should Be Equal As Integers    ${rc}  0

Check if wazuh configuration reads back
    ${output}  ${rc} =    Execute Command    api-cli run module/${module_id}/get-configuration --data '{}'
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}  0
    ${config} =    Evaluate    json.loads('''${output}''')    modules=json
    Should Be Equal    ${config}[host]    ${TEST_HOST}
    Should Be Equal    ${config}[ldap_domain]    ${EMPTY}
    Should Be Equal    ${config}[export_url]    ${EMPTY}

Check if the three services are running
    FOR    ${service}    IN    wazuh-indexer    wazuh-manager    wazuh-dashboard
        ${output}  ${rc} =    Execute Command
        ...    runagent -m ${module_id} systemctl --user is-active ${service}.service
        ...    return_rc=True
        Should Be Equal As Integers    ${rc}  0
        Should Be Equal    ${output}    active
    END

Check if the agent ports are open on the node
    FOR    ${port}    IN    1514    1515    1517
        ${rc} =    Execute Command    ss -ltn | grep -q ':${port} '
        ...    return_rc=True  return_stdout=False
        Should Be Equal As Integers    ${rc}  0
    END

Check if wazuh reports its health
    ${output}  ${rc} =    Execute Command    api-cli run module/${module_id}/get-health --data '{}'
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}  0
    ${health} =    Evaluate    json.loads('''${output}''')    modules=json
    Should Be Equal    ${health}[indexer][status]    green

Check if an enrollment token is created
    ${output}  ${rc} =    Execute Command
    ...    api-cli run module/${module_id}/get-enrollment-token --data '{"max_uses":1,"description":"robot"}'
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}  0
    ${token} =    Evaluate    json.loads('''${output}''')    modules=json
    Should Be Equal    ${token}[address]    ${TEST_HOST}
    Should Not Be Empty    ${token}[token]

Check if the certificates can be issued again
    ${rc} =    Execute Command    api-cli run module/${module_id}/renew-certificates
    ...    return_rc=True  return_stdout=False
    Should Be Equal As Integers    ${rc}  0
    ${rc} =    Execute Command    runagent -m ${module_id} systemctl --user is-active wazuh-manager.service
    ...    return_rc=True  return_stdout=False
    Should Be Equal As Integers    ${rc}  0

Check if wazuh is removed correctly
    ${rc} =    Execute Command    remove-module --no-preserve ${module_id}
    ...    return_rc=True  return_stdout=False
    Should Be Equal As Integers    ${rc}  0
