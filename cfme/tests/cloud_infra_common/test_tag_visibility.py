import fauxfactory
import pytest

from cfme import test_requirements
from cfme.cloud.provider import CloudProvider
from cfme.exceptions import ItemNotFound
from cfme.infrastructure.provider import InfraProvider
from cfme.markers.env_markers.provider import ONE
from cfme.markers.env_markers.provider import ONE_PER_TYPE
from cfme.utils.appliance.implementations.ui import navigate_to

pytestmark = [
    test_requirements.tag,
    pytest.mark.tier(3),
    pytest.mark.provider(
        [CloudProvider, InfraProvider], required_fields=['cap_and_util'], selector=ONE_PER_TYPE
    ),
    pytest.mark.usefixtures('setup_provider')
]


@pytest.fixture
def tagged_vm(tag, provider):
    ownership_vm = provider.data.cap_and_util.capandu_vm
    collection = provider.appliance.provider_based_collection(provider)
    tag_vm = collection.instantiate(ownership_vm, provider)
    tag_vm.add_tag(tag=tag)
    yield tag_vm
    tag_vm.appliance.server.login_admin()
    tag_vm.remove_tag(tag=tag)


@pytest.mark.rhv3
def test_tag_vis_vm(tagged_vm, user_restricted):
    """
    Polarion:
        assignee: anikifor
        casecomponent: Tagging
        initialEstimate: 1/4h
    """
    with user_restricted:
        assert tagged_vm.exists, "vm not found"


# For now use existing tags as for bz 1579867, should be replaced with random created tag fixture
@pytest.fixture(scope='module')
def location_tag(appliance):
    """Existing tag object"""
    category = appliance.collections.categories.instantiate(
        name='location', display_name='Location'
    )
    tag = category.collections.tags.instantiate(name='paris', display_name='Paris')
    return tag


# For now use existing tags as for bz 1579867, should be replaced with random created tag fixture
@pytest.fixture(scope='module')
def service_level_tag(appliance):
    """Existing tag object"""
    category = appliance.collections.categories.instantiate(
        name='service_level', display_name='Service Level'
    )
    tag = category.collections.tags.instantiate(
        name='silver',
        display_name='Silver'
    )
    return tag


@pytest.fixture(scope='module')
def vms_for_tagging(provider, appliance):
    """Get two existing vms for tagging"""
    view = navigate_to(provider, 'ProviderVms')
    all_names = view.entities.all_entity_names
    first_vm = appliance.collections.infra_vms.instantiate(name=all_names[0], provider=provider)
    second_vm = appliance.collections.infra_vms.instantiate(name=all_names[1], provider=provider)
    return first_vm, second_vm


@pytest.fixture
def group_with_tag_expression(appliance, user_restricted, request):
    def _group_with_tag_expression(expression):
        """Updates group with provided expression, also assign user to group"""
        group = appliance.collections.groups.create(
            description='grp{}'.format(fauxfactory.gen_alphanumeric()),
            role='EvmRole-approver',
            tag=expression
        )
        request.addfinalizer(group.delete)
        user_restricted.update({'group': group})
        return group

    return _group_with_tag_expression


@pytest.fixture
def check_vm_visibility(user_restricted, appliance):
    def _check_vm_visibility(group, vm, vis_expect):
        """
        Args:
            group: restricted group with expression tag
            vm: vm object to check visibility
            vis_expect: bool, True if tag should be visible

        Returns: None
        """
        with user_restricted:
            view = navigate_to(appliance.server, 'LoggedIn')

            orig_group = view.current_groupname
            if group.description != orig_group:
                view.change_group(group.description)
            try:
                navigate_to(vm, 'VMsOnlyDetails')
                actual_visibility = True
            except ItemNotFound:
                actual_visibility = False
        assert actual_visibility == vis_expect, (
            'VM visibility is not as expected, expected {}'.format(vis_expect)
        )
    return _check_vm_visibility


@pytest.mark.provider([InfraProvider], override=True, selector=ONE, scope='module')
def test_tag_expression_and_condition(
    request, vms_for_tagging, location_tag,
    service_level_tag, group_with_tag_expression, check_vm_visibility
):
    """Test for tag expression with AND condition
        Steps:
        1. Create group with expression tag1 AND tag2
        2. Assign tag1 to vm1 -> vm should not be visible to restricted user
        3. Assign tag2 to vm1 -> vm should be visible to restricted user

    Polarion:
        assignee: anikifor
        casecomponent: Tagging
        initialEstimate: 1/4h
    """
    first_vm, _ = vms_for_tagging
    group = group_with_tag_expression(';select_first_expression;click_and;'.join(
        ['fill_tag(My Company Tags : {}, {})'.format(
            tag.category.display_name, tag.display_name)
            for tag in [location_tag, service_level_tag]]))

    first_vm.add_tag(location_tag)
    request.addfinalizer(lambda: first_vm.remove_tag(location_tag))
    check_vm_visibility(group, first_vm, False)

    first_vm.add_tag(service_level_tag)
    request.addfinalizer(lambda: first_vm.remove_tag(service_level_tag))
    check_vm_visibility(group, first_vm, True)


@pytest.mark.provider([InfraProvider], override=True, selector=ONE, scope='module')
def test_tag_expression_or_condition(
    request, vms_for_tagging, location_tag,
    service_level_tag, group_with_tag_expression, check_vm_visibility
):
    """Test for tag expression with OR condition
        Steps:
        1. Create group with expression tag1 OR tag2
        2. Assign tag1 to vm1 -> vm should be visible to restricted user
        3. Assign tag2 to vm2 -> vm should be visible to restricted user

    Polarion:
        assignee: anikifor
        casecomponent: Tagging
        initialEstimate: 1/4h
    """
    first_vm, second_vm = vms_for_tagging
    group = group_with_tag_expression(';select_first_expression;click_or;'.join(
        ['fill_tag(My Company Tags : {}, {})'.format(
            tag.category.display_name, tag.display_name)
            for tag in [location_tag, service_level_tag]]))

    first_vm.add_tag(location_tag)
    request.addfinalizer(lambda: first_vm.remove_tag(location_tag))
    check_vm_visibility(group, first_vm, True)

    second_vm.add_tag(service_level_tag)
    request.addfinalizer(lambda: second_vm.remove_tag(service_level_tag))
    check_vm_visibility(group, second_vm, True)


@pytest.mark.provider([InfraProvider], override=True, selector=ONE, scope='module')
def test_tag_expression_not_condition(
    request, vms_for_tagging, location_tag,
    group_with_tag_expression, check_vm_visibility
):
    """Test for tag expression with NOT condition
        Steps:
        1. Create group with expression NOT tag1
        2. Assign tag1 to vm1 -> vm should not be visible to restricted user
        3. vm2 should be visible to restricted user

    Polarion:
        assignee: anikifor
        casecomponent: Tagging
        initialEstimate: 1/4h
    """
    first_vm, second_vm = vms_for_tagging
    group = group_with_tag_expression('{};select_first_expression;click_not;'.format(
        'fill_tag(My Company Tags : {}, {})'.format(
            location_tag.category.display_name, location_tag.display_name)))
    first_vm.add_tag(location_tag)
    request.addfinalizer(lambda: first_vm.remove_tag(location_tag))
    check_vm_visibility(group, first_vm, False)

    check_vm_visibility(group, second_vm, True)


@pytest.mark.provider([InfraProvider], override=True, selector=ONE, scope='module')
def test_tag_expression_not_and_condition(
        request, vms_for_tagging, location_tag,
        service_level_tag, group_with_tag_expression,
        check_vm_visibility
):
    """Test for tag expression with NOT and AND condition
        Steps:
        1. Create group with expression NOT tag1 AND tag2
        2. Assign tag1 to vm1 -> vm should not be visible to restricted user
        3. Assign tag2 to vm1 -> vm should not be visible to restricted user
        4. Assign tag2 to vm2 -> vm should be visible to restricted user

    Polarion:
        assignee: anikifor
        casecomponent: Tagging
        initialEstimate: 1/4h
    """
    first_vm, second_vm = vms_for_tagging
    group = group_with_tag_expression(
        ';select_first_expression;click_not;select_first_expression;click_and;'.join(
            ['fill_tag(My Company Tags : {}, {})'.format(
                tag.category.display_name, tag.display_name)
                for tag in [location_tag, service_level_tag]]))

    first_vm.add_tag(location_tag)
    request.addfinalizer(lambda: first_vm.remove_tag(location_tag))
    check_vm_visibility(group, first_vm, False)

    first_vm.add_tag(service_level_tag)
    request.addfinalizer(lambda: first_vm.remove_tag(service_level_tag))
    check_vm_visibility(group, first_vm, False)

    second_vm.add_tag(service_level_tag)
    request.addfinalizer(lambda: second_vm.remove_tag(service_level_tag))
    check_vm_visibility(group, second_vm, True)


@pytest.mark.provider([InfraProvider], override=True, selector=ONE, scope='module')
def test_tag_expression_not_or_condition(
    request, vms_for_tagging, location_tag, service_level_tag, group_with_tag_expression,
    check_vm_visibility
):
    """Test for tag expression with NOT and OR condition
        Steps:
        1. Create group with expression NOT tag1 OR tag2
        2. Assign tag1 to vm1 -> vm should not be visible to restricted user
        3. Assign tag2 to vm1 -> vm should be visible to restricted user

    Polarion:
        assignee: anikifor
        casecomponent: Tagging
        initialEstimate: 1/4h
    """
    first_vm, _ = vms_for_tagging
    group = group_with_tag_expression(
        ';select_first_expression;click_not;select_first_expression;click_or;'.join(
            ['fill_tag(My Company Tags : {}, {})'.format(
                tag.category.display_name, tag.display_name)
                for tag in [location_tag, service_level_tag]]))

    first_vm.add_tag(location_tag)
    request.addfinalizer(lambda: first_vm.remove_tag(location_tag))
    check_vm_visibility(group, first_vm, False)

    first_vm.add_tag(service_level_tag)
    request.addfinalizer(lambda: first_vm.remove_tag(service_level_tag))
    check_vm_visibility(group, first_vm, True)


@pytest.mark.manual
@pytest.mark.tier(2)
def test_tag_expression_and_with_or_with_not():
    """
    Polarion:
        assignee: anikifor
        casecomponent: Tagging
        caseimportance: medium
        initialEstimate: 1/8h
        startsin: 5.9
        testSteps:
            1. Combine tags with AND and NOT and OR conditions
            2. Check item visibility
    """
    pass


@pytest.mark.manual
@pytest.mark.tier(2)
def test_tag_expression_and_with_or():
    """
    Polarion:
        assignee: anikifor
        casecomponent: Tagging
        caseimportance: medium
        initialEstimate: 1/8h
        startsin: 5.9
        testSteps:
            1. Combine tags with AND and OR conditions
            2. Check item visibility
    """
    pass
