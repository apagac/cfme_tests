"""V2V tests to validate functional and non-function UI usecases"""
import fauxfactory
import pytest
from widgetastic.exceptions import NoSuchElementException

from cfme import test_requirements
from cfme.cloud.provider.openstack import OpenStackProvider
from cfme.fixtures.provider import rhel7_minimal
from cfme.fixtures.v2v_fixtures import infra_mapping_default_data
from cfme.infrastructure.provider.rhevm import RHEVMProvider
from cfme.infrastructure.provider.virtualcenter import VMwareProvider
from cfme.markers.env_markers.provider import ONE_PER_TYPE
from cfme.markers.env_markers.provider import ONE_PER_VERSION
from cfme.tests.services.test_service_rbac import new_group
from cfme.tests.services.test_service_rbac import new_role
from cfme.tests.services.test_service_rbac import new_user
from cfme.utils.appliance.implementations.ui import navigate_to
from cfme.v2v.migration_plans import MigrationPlanRequestDetailsView

pytestmark = [
    test_requirements.v2v,
    pytest.mark.provider(
        classes=[RHEVMProvider, OpenStackProvider],
        selector=ONE_PER_VERSION,
        required_flags=["v2v"],
        scope="module"
    ),
    pytest.mark.provider(
        classes=[VMwareProvider],
        selector=ONE_PER_TYPE,
        fixture_name="source_provider",
        required_flags=["v2v"],
        scope="module"
    ),
    pytest.mark.usefixtures("v2v_provider_setup")
]


@pytest.mark.tier(1)
def test_v2v_infra_map_data(request, appliance, source_provider, provider, soft_assert):
    """
    Test to validate infra map data

    Polarion:
        assignee: ytale
        initialEstimate: 1/2h
        caseimportance: critical
        caseposneg: positive
        testtype: functional
        startsin: 5.10
        casecomponent: V2V
        testSteps:
            1. Add source and target provider
            2. Create infra map
            3. Test infra map UI
    """
    map_data = infra_mapping_default_data(source_provider, provider)
    map_collection = appliance.collections.v2v_infra_mappings
    mapping = map_collection.create(**map_data)

    @request.addfinalizer
    def _cleanup():
        map_collection.delete(mapping)
    view = navigate_to(map_collection, "All")
    mapping_list = view.infra_mapping_list

    # Test1: Check custom map in infra map list
    soft_assert(mapping.name in mapping_list.read())

    # Test2: Validate infra map description
    soft_assert(str(mapping_list.get_map_description(mapping.name)) == mapping.description)

    # Test3: Source cluster from UI
    soft_assert(mapping.clusters[0].sources[0].format() in
                mapping_list.get_map_source_clusters(mapping.name)[0])

    # Test4: Target cluster from UI
    soft_assert(mapping.clusters[0].targets[0].format() in
                mapping_list.get_map_target_clusters(mapping.name)[0])

    # Test5: Source datastore from UI
    soft_assert(mapping.datastores[0].sources[0].format() in
                mapping_list.get_map_source_datastores(mapping.name)[0])

    # Test6: Target datastore from UI
    soft_assert(mapping.datastores[0].targets[0].format() in
                mapping_list.get_map_target_datastores(mapping.name)[0])

    # Test5: Source network from UI
    soft_assert(mapping.networks[0].sources[0].format() in
                mapping_list.get_map_source_networks(mapping.name)[0])

    # Test6: Target network from UI
    soft_assert(mapping.networks[0].targets[0].format() in
                mapping_list.get_map_target_networks(mapping.name)[0])


@pytest.mark.tier(1)
def test_v2v_infra_map_ui(appliance, source_provider, provider, soft_assert):
    """
    Test to validate non-functional UI tests on infrastructure mappings wizard

    Polarion:
        assignee: ytale
        initialEstimate: 1/2h
        caseimportance: critical
        caseposneg: positive
        testtype: functional
        startsin: 5.10
        casecomponent: V2V
        testSteps:
            1. Add source and target provider
            2. Create infra map
            3. Validate non-functional tests
    """
    map_collection = appliance.collections.v2v_infra_mappings
    map_name = fauxfactory.gen_string("alphanumeric", length=26)
    map_description = fauxfactory.gen_string("alphanumeric", length=130)
    map_data = infra_mapping_default_data(source_provider, provider)
    view = navigate_to(map_collection, "Add")

    # Test1: 24 characters can be entered in name field
    view.general.name.fill(map_name)
    soft_assert(len(view.general.name.read()) == 24)

    # Test2: 128 characters can be entered in description field
    view.general.name.fill(map_name)
    view.general.description.fill(map_description)
    soft_assert(len(view.general.description.read()) == 128)
    if map_data['plan_type'] == "osp":
        view.general.plan_type.fill("Red Hat OpenStack Platform")
    view.general.next_btn.click()

    # Test3: Source and target clusters can be mapped
    cluster_view = view.cluster.MappingFillView(object_type='cluster')
    cluster_view.wait_displayed("5s")
    cluster_data = {
        'source': map_data['clusters'][0].sources, 'target': map_data['clusters'][0].targets}
    soft_assert(len(cluster_view.source.all_items) > 0)
    soft_assert(len(cluster_view.target.all_items) > 0)
    soft_assert(
        view.cluster.add_mapping.root_browser.get_attribute('disabled', view.cluster.add_mapping))
    cluster_view.fill(cluster_data)

    # Test4: Multiple source and single target clusters can be mapped
    view.general.remove_all_mappings.click()
    cluster_data = {
        'source': cluster_view.source.all_items, 'target': map_data['clusters'][0].targets}
    cluster_view.fill(cluster_data)
    view.general.next_btn.click()

    # Test5: Single source and single target datastores can be mapped
    datastore_view = view.datastore.MappingFillView(object_type='datastore')
    datastore_view.wait_displayed("5s")
    datastore_data = {
        'source': map_data['datastores'][0].sources, 'target': map_data['datastores'][0].targets}
    soft_assert(len(datastore_view.source.all_items) > 0)
    soft_assert(len(datastore_view.target.all_items) > 0)
    soft_assert(view.datastore.add_mapping.root_browser.get_attribute(
        'disabled', view.datastore.add_mapping))
    datastore_view.fill(datastore_data)

    # Test6: Multiple source and single target datastores mapping
    view.general.remove_all_mappings.click()
    datastore_data = {
        'source': datastore_view.source.all_items, 'target': map_data['datastores'][0].targets}
    datastore_view.fill(datastore_data)
    view.general.next_btn.click()

    # Test7: Single source and single target networks can be mapped
    network_view = view.network.MappingFillView(object_type='network')
    network_view.wait_displayed("5s")
    network_data = {
        'source': map_data['networks'][0].sources, 'target': map_data['networks'][0].targets}
    soft_assert(len(network_view.source.all_items) > 0)
    soft_assert(len(network_view.target.all_items) > 0)
    soft_assert(
        view.network.add_mapping.root_browser.get_attribute('disabled', view.network.add_mapping))
    network_view.fill(network_data)

    # Test8: Multiple source and single target networks can be mapped
    view.general.remove_all_mappings.click()
    network_data = {
        'source': network_view.source.all_items, 'target': map_data['networks'][0].targets}
    network_view.fill(network_data)
    view.general.create_btn.click()
    view.result.close_btn.click()

    # Test9: Map with duplicate name
    view = navigate_to(map_collection, 'Add')
    view.general.name.fill(map_name)
    view.general.description.fill(map_description)
    soft_assert('a unique name' in view.general.name_help_text.read())


@pytest.mark.tier(1)
def test_v2v_plan_ui(
        request, appliance, source_provider, provider, mapping_data_vm_obj_mini, soft_assert):
    """
    Test to validate non-functional UI tests on migration plan wizard

    Polarion:
        assignee: ytale
        initialEstimate: 2/4h
        caseimportance: critical
        caseposneg: positive
        testtype: functional
        startsin: 5.10
        casecomponent: V2V
        testSteps:
            1. Add source and target provider
            2. Create migration plan
            3. Validate non-functional tests
    """
    map_collection = appliance.collections.v2v_infra_mappings
    plan_collection = appliance.collections.v2v_migration_plans
    plan_name = fauxfactory.gen_string("alphanumeric", length=10)
    plan_description = fauxfactory.gen_string("alphanumeric", length=10)
    map_data = infra_mapping_default_data(source_provider, provider)
    mapping = map_collection.create(**map_data)

    @request.addfinalizer
    def _cleanup():
        map_collection.delete(mapping)
    view = navigate_to(plan_collection, "Add")

    # Test1: Migration plan name check
    view.general.infra_map.select_by_visible_text(mapping.name)
    soft_assert(view.general.infra_map.read() == mapping.name)

    # Test2: 24 characters can be entered in name field of migration plan
    view.general.name.fill(fauxfactory.gen_string("alphanumeric", length=26))
    soft_assert(len(view.general.name.read()) == 24)
    view.general.name.fill(plan_name)

    # Test3: 128 characters can be entered in description field of migration plan
    view.general.description.fill(fauxfactory.gen_string("alphanumeric", length=130))
    soft_assert(len(view.general.description.read()) == 128)
    view.general.description.fill(plan_description)
    view.next_btn.click()
    view.vms.wait_displayed()

    # Test4: VM number count check
    soft_assert(len([row for row in view.vms.table.rows()]) > 0)
    view.vms.fill({"vm_list": mapping_data_vm_obj_mini.vm_list})
    if map_data['plan_type'] == "osp":
        view.instance_properties.wait_displayed()
        view.next_btn.click()
    view.advanced.wait_displayed()
    view.next_btn.click()
    view.schedule.run_migration.select("Save migration plan to run later")
    view.schedule.create.click()
    view.close_btn.click()

    # Test5: Plan name displayed in migration plan list page
    new_view = navigate_to(plan_collection, "NotStarted")
    soft_assert(plan_name in new_view.plans_not_started_list.read())

    # Test6: Plan description displayed in migration plan list page
    soft_assert(new_view.plans_not_started_list.get_plan_description(plan_name) == plan_description)

    # Test7: VM number displayed in migration plan list page
    soft_assert(str(len(mapping_data_vm_obj_mini.vm_list)) in
                new_view.plans_not_started_list.get_vm_count_in_plan(plan_name))
    new_view.plans_not_started_list.select_plan(plan_name)
    new_view = appliance.browser.create_view(MigrationPlanRequestDetailsView, wait='10s')
    new_view.items_on_page.item_select("15")

    # Test8: Plan with duplicate name
    view = navigate_to(plan_collection, "Add")
    view.general.wait_displayed()
    view.general.infra_map.select_by_visible_text(mapping.name)
    view.general.name.fill(plan_name)
    view.general.description.fill(fauxfactory.gen_string("alphanumeric", length=10))
    soft_assert("a unique name" in view.general.name_help_text.read())
    view.cancel_btn.click()

    # Test9: Associated plan check
    view = navigate_to(map_collection, "All")
    soft_assert(
        view.infra_mapping_list.get_associated_plans_count(mapping.name) == '1 Associated Plan')
    soft_assert(view.infra_mapping_list.get_associated_plans(mapping.name) == plan_name)


@pytest.mark.tier(3)
def test_v2v_infra_map_special_chars(request, appliance, source_provider, provider, soft_assert):
    """
    Test infra map with special characters

    Polarion:
        assignee: ytale
        initialEstimate: 1/2h
        caseimportance: low
        caseposneg: positive
        testtype: functional
        startsin: 5.10
        casecomponent: V2V
        testSteps:
            1. Add source and target provider
            2. Create infra map with special characters
    """
    map_collection = appliance.collections.v2v_infra_mappings
    map_data = infra_mapping_default_data(source_provider, provider)
    map_data["name"] = fauxfactory.gen_special(length=4)
    mapping = map_collection.create(**map_data)

    @request.addfinalizer
    def _cleanup():
        map_collection.delete(mapping)
    view = navigate_to(map_collection, "All")
    soft_assert(mapping.name in view.infra_mapping_list.read())
    view.infra_mapping_list.delete_mapping(mapping.name)
    view.wait_displayed()
    try:
        assert mapping.name not in view.infra_mapping_list.read()
    except NoSuchElementException:
        # meaning there was only one mapping that is deleted, list is empty
        pass


@pytest.mark.uncollectif(lambda provider: provider.one_of(OpenStackProvider))
def test_v2v_rbac(appliance, new_credential):
    """
    Test migration with role-based access control

    Polarion:
        assignee: ytale
        initialEstimate: 1/2h
        caseimportance: high
        caseposneg: positive
        testtype: functional
        startsin: 5.10
        casecomponent: V2V
    """
    role = new_role(appliance=appliance,
                    product_features=[(['Everything'], True)])
    group = new_group(appliance=appliance, role=role.name)
    user = new_user(appliance=appliance, group=group, credential=new_credential)

    product_features = [(['Everything', 'Compute', 'Migration'], False)]
    role.update({'product_features': product_features})
    with user:
        view = navigate_to(appliance.server, 'Dashboard')
        nav_tree = view.navigation.nav_item_tree()
        # Checks migration option is disabled in navigation
        assert 'Migration' not in nav_tree['Compute'], ('Migration found in nav tree, '
                                                        'rbac should not allow this')

    product_features = [(['Everything'], True)]
    role.update({'product_features': product_features})
    with user:
        view = navigate_to(appliance.server, 'Dashboard', wait_for_view=15)
        nav_tree = view.navigation.nav_item_tree()
        # Checks migration option is enabled in navigation
        assert 'Migration' in nav_tree['Compute'], ('Migration not found in nav tree, '
                                                    'rbac should allow this')


@pytest.mark.tier(1)
@pytest.mark.parametrize(
    'mapping_data_vm_obj_single_datastore', [['iscsi', 'iscsi', rhel7_minimal]], indirect=True)
def test_v2v_infra_map_edit(request, appliance, source_provider, provider,
                            mapping_data_vm_obj_single_datastore, soft_assert):
    """
    Test migration by editing migration mapping fields

    Polarion:
        assignee: ytale
        initialEstimate: 1/2h
        caseimportance: high
        caseposneg: positive
        testtype: functional
        startsin: 5.10
        casecomponent: V2V
    """
    map_collection = appliance.collections.v2v_infra_mappings
    mapping_data = infra_mapping_default_data(source_provider, provider)
    mapping = map_collection.create(**mapping_data)

    @request.addfinalizer
    def _cleanup():
        map_collection.delete(mapping)

    edited_mapping = mapping_data_vm_obj_single_datastore.infra_mapping_data
    mapping.update(edited_mapping)
    view = navigate_to(map_collection, 'All')
    mapping_list = view.infra_mapping_list

    # Test1: Check custom map in infra map list
    soft_assert(mapping.name in mapping_list.read())

    # Test2: Validate infra map description
    soft_assert(mapping.description == str(mapping_list.get_map_description(mapping.name)))

    # Test3: Source cluster from UI
    soft_assert(mapping.clusters[0].sources[0].format() in
                mapping_list.get_map_source_clusters(mapping.name)[0])

    # Test4: Target cluster from UI
    soft_assert(mapping.clusters[0].targets[0].format() in
                mapping_list.get_map_target_clusters(mapping.name)[0])

    # Test5: Source datastore from UI
    soft_assert(mapping.datastores[0].sources[0].format() in
                mapping_list.get_map_source_datastores(mapping.name)[0])

    # Test6: Target datastore from UI
    soft_assert(mapping.datastores[0].targets[0].format() in
                mapping_list.get_map_target_datastores(mapping.name)[0])

    # Test5: Source network from UI
    soft_assert(mapping.networks[0].sources[0].format() in
                mapping_list.get_map_source_networks(mapping.name)[0])

    # Test6: Target network from UI
    soft_assert(mapping.networks[0].targets[0].format() in
                mapping_list.get_map_target_networks(mapping.name)[0])


@pytest.mark.tier(2)
def test_v2v_with_no_providers(appliance, source_provider, provider, soft_assert):
    """
    Test V2V UI with no source and target provider

    Polarion:
        assignee: ytale
        initialEstimate: 1/2h
        caseimportance: high
        caseposneg: positive
        testtype: functional
        startsin: 5.10
        casecomponent: V2V
        testSteps:
            1. Remove source and target providers
            2. Check can we add infra map
            3. Add providers back
    """
    map_collection = appliance.collections.v2v_infra_mappings
    is_source_provider_deleted = source_provider.delete_if_exists(cancel=False)
    is_target_provider_deleted = provider.delete_if_exists(cancel=False)
    view = navigate_to(map_collection, "All")

    # Test1: Check 'Configure provider' get displayed after provider deletion
    soft_assert(view.configure_providers.is_displayed)

    # Test2: Check 'add infra map' don't get displayed on overview page
    soft_assert(not view.create_infra_mapping.is_displayed)

    # Adding provider back to the test
    if is_source_provider_deleted:
        source_provider.create(validate_inventory=True)
    if is_target_provider_deleted:
        provider.create(validate_inventory=True)
