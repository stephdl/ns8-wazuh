#!/bin/bash

#
# Copyright (C) 2023 Nethesis S.r.l.
# SPDX-License-Identifier: GPL-3.0-or-later
#

# Terminate on error
set -e

# Prepare variables for later use
images=()
# The image will be pushed to GitHub container registry
repobase="${REPOBASE:-ghcr.io/nethserver}"
# Configure the image name
reponame="wazuh"
wazuh_manager_image="docker.io/wazuh/wazuh-manager:5.0.0-rc1"
wazuh_indexer_image="docker.io/wazuh/wazuh-indexer:5.0.0-rc1"
wazuh_dashboard_image="docker.io/wazuh/wazuh-dashboard:5.0.0-rc1"

# Extract the upstream version from the image tag, to set it in the metadata
wazuh_upstream_version="${wazuh_manager_image##*:}"
metadata_file="ui/public/metadata.json"
metadata_backup=$(mktemp)

cleanup() {
    cp "${metadata_backup}" "${metadata_file}"
    rm -f "${metadata_backup}"
}

cp "${metadata_file}" "${metadata_backup}"
trap cleanup EXIT

jq --arg v "${wazuh_upstream_version}" \
   '.upstream_name |= gsub("version set automatically"; $v)' \
   "${metadata_file}" > "${metadata_file}.tmp" && mv "${metadata_file}.tmp" "${metadata_file}"

# Create a new empty container image
container=$(buildah from scratch)

# Reuse existing nodebuilder-wazuh container, to speed up builds
if ! buildah containers --format "{{.ContainerName}}" | grep -q nodebuilder-wazuh; then
    echo "Pulling NodeJS runtime..."
    buildah from --name nodebuilder-wazuh -v "${PWD}:/usr/src:Z" docker.io/library/node:lts
fi

echo "Build static UI files with node..."
buildah run \
    --workingdir=/usr/src/ui \
    --env="NODE_OPTIONS=--openssl-legacy-provider" \
    nodebuilder-wazuh \
    sh -c "corepack enable && yarn install && yarn build"

# Add imageroot directory to the container image
buildah add "${container}" imageroot /imageroot
# list-agents reads AGENT_SETUP in it, to find the agents set up by an older script
buildah add "${container}" scripts/install-agent.sh /imageroot/etc/install-agent.sh
buildah add "${container}" ui/dist /ui

buildah config --entrypoint=/ \
    --label="org.nethserver.authorizations=node:fwadm traefik@node:routeadm cluster:accountconsumer" \
    --label="org.nethserver.max-per-node=1" \
    --label="org.nethserver.tcp-ports-demand=1" \
    --label="org.nethserver.volumes=wazuh-indexer-data wazuh-snapshots wazuh-logs" \
    --label="org.nethserver.rootfull=0" \
    --label="org.nethserver.min-core=3.20.1" \
    --label="org.nethserver.images=${wazuh_manager_image} ${wazuh_indexer_image} ${wazuh_dashboard_image}" \
    "${container}"
# Commit the image
buildah commit "${container}" "${repobase}/${reponame}"

# Append the image URL to the images array
images+=("${repobase}/${reponame}")

#
# NOTICE:
#
# It is possible to build and publish multiple images.
#
# 1. create another buildah container
# 2. add things to it and commit it
# 3. append the image url to the images array
#

#
# Setup CI when pushing to Github. 
# Warning! docker::// protocol expects lowercase letters (,,)
if [[ -n "${CI}" ]]; then
    # Set output value for Github Actions
    printf "images=%s\n" "${images[*],,}" >> "${GITHUB_OUTPUT}"
else
    # Just print info for manual push
    printf "Publish the images with:\n\n"
    for image in "${images[@],,}"; do printf "  buildah push %s docker://%s:%s\n" "${image}" "${image}" "${IMAGETAG:-latest}" ; done
    printf "\n"
fi
