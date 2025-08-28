#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for Netbox SAML integration."""
import logging

import jubilant
import requests
import pytest
from tests.integration.types import App

logger = logging.getLogger(__name__)

@pytest.mark.usefixtures("netbox_saml_integration")
def test_saml_integration(
    netbox_nginx_integration: App,
    juju: jubilant.Juju,
    saml_helper,
    s3_netbox_configuration,
    s3_netbox_credentials,
    netbox_hostname: str,
):
    """
    arrange: Integrate the Charm with saml-integrator, with a real SP.
    act: Call the endpoint to get env variables.
    assert: Valid Saml env variables should be in the workload.
    """
    # The goal of this test is not to test Saml in a real application, as it is not really
    # necessary, but that the integration with the saml-integrator is correct and the Saml
    # variables get injected into the workload.
    # However, for saml-integrator to get the metadata, we need a real SP, so SamlK8sTestHelper is
    # used to not have a dependency to an external SP.

    # model_name = juju.status().model.name

    saml_integrator_app_name = "saml-integrator"
    # status = juju.status()
    # if saml_integrator_app_name not in status.apps:
    #     juju.deploy(
    #         saml_integrator_app_name,
    #         channel="latest/edge",
    #         base="ubuntu@22.04",
    #         trust=True,
    #     )
    #     juju.wait(
    #         lambda status: jubilant.all_agents_idle(status, saml_integrator_app_name),
    #         timeout=600,
    #     )
    # saml_helper = SamlK8sTestHelper.deploy_saml_idp(model_name, kube_config="/var/snap/microk8s/current/credentials/client.config")# , 

    # saml_helper.prepare_pod(model_name, f"{saml_integrator_app_name}-0")
    # saml_helper.prepare_pod(model_name, f"{netbox_nginx_integration.name}-0")
    # juju.config(
    #     netbox_nginx_integration.name,{
    #         "saml-sp-entity-id": f"https://{netbox_hostname}",
    #         # The saml Name for FriendlyName "uid"
    #         "saml-username": "urn:oid:0.9.2342.19200300.100.1.1",})
    # juju.config(
    #     saml_integrator_app_name,
    #     {
    #         "entity_id": saml_helper.entity_id,
    #         "metadata_url": saml_helper.metadata_url,
    #     },
    # )
    # try:
    #     juju.integrate(saml_integrator_app_name, netbox_nginx_integration.name)
    # except jubilant.CLIError as e:
    #     if "already exists" in str(e):
    #         logger.warning("The relation already exists.")
    #     else:
    #         raise e

    juju.wait(
        lambda status: jubilant.all_active(status, saml_integrator_app_name, netbox_nginx_integration.name),
        timeout=600,
    )
    res = requests.get(
        "https://127.0.0.1/",
        headers={"Host": netbox_hostname},
        verify=False,
        timeout=30,  # nosec
    )
    assert res.status_code == 200
    assert "<title>Home | NetBox</title>" in res.text
    # The user is not logged in.
    assert "Log Out" not in res.text
    assert "ubuntu" not in res.text

    session = requests.session()

    # Act part. Log in with SAML.
    redirect_url = "https://127.0.0.1/oauth/login/saml/?next=%2F&idp=saml"
    res = session.get(
        redirect_url,
        headers={"Host": netbox_hostname},
        timeout=5,
        verify=False,
        allow_redirects=False,
    )
    assert res.status_code == 302
    redirect_url = res.headers["Location"]
    saml_response = saml_helper.redirect_sso_login(redirect_url)
    assert f"https://{netbox_hostname}" in saml_response.url

    # Assert part. Check that the user is logged in.
    url = saml_response.url.replace(f"https://{netbox_hostname}", "https://127.0.0.1")
    logged_in_page = session.post(
        url, data=saml_response.data, headers={"Host": netbox_hostname}, timeout=10, verify=False
    )
    assert logged_in_page.status_code == 200
    assert "<title>Home | NetBox</title>" in logged_in_page.text
    # The user is logged in.
    assert "Log Out" in logged_in_page.text
    assert "ubuntu" in logged_in_page.text
    assert "ubuntu" in logged_in_page.text
