*** Settings ***
Library           SSHLibrary

*** Variables ***
${SSH_KEYFILE}    %{HOME}/.ssh/id_ecdsa
# NODE_ADDR must be the cluster leader, which runs add-module and api-cli. The module and the agent
# go on INSTALL_NODE, reached at INSTALL_ADDR: by default the leader itself, as on the CI single node.
${INSTALL_NODE}    1
${INSTALL_ADDR}    ${EMPTY}

*** Keywords ***
Connect to the node
    Open Connection   ${NODE_ADDR}    alias=leader
    Login With Public Key    root    ${SSH_KEYFILE}
    ${output} =    Execute Command    systemctl is-system-running  --wait
    Should Be True    '${output}' == 'running' or '${output}' == 'degraded'
    # The module may go on another node of the cluster, see INSTALL_NODE above
    ${install_addr} =    Set Variable If    '${INSTALL_ADDR}' == ''    ${NODE_ADDR}    ${INSTALL_ADDR}
    Set Global Variable    ${INSTALL_NODE}
    Open Connection   ${install_addr}    alias=install
    Login With Public Key    root    ${SSH_KEYFILE}

*** Settings ***
Suite Setup       Connect to the Node
