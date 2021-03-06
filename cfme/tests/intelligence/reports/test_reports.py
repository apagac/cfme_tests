import fauxfactory
import pytest

from cfme import test_requirements
from cfme.infrastructure.provider import InfraProvider
from cfme.intelligence.reports.reports import ReportDetailsView
from cfme.markers.env_markers.provider import ONE_PER_CATEGORY
from cfme.rest.gen_data import users as _users
from cfme.utils.conf import cfme_data
from cfme.utils.ftp import FTPClientWrapper
from cfme.utils.log_validator import LogValidator
from cfme.utils.rest import assert_response

pytestmark = [test_requirements.report, pytest.mark.tier(3), pytest.mark.sauce]


@pytest.fixture
def get_report(appliance, request):
    def _report(file_name, menu_name):
        collection = appliance.collections.reports

        # download the report from server
        fs = FTPClientWrapper(cfme_data.ftpserver.entities.reports)
        file_path = fs.download(file_name)

        # import the report
        collection.import_report(file_path)

        # instantiate report and return it
        report = collection.instantiate(
            type="My Company (All Groups)", subtype="Custom", menu_name=menu_name
        )
        request.addfinalizer(report.delete_if_exists)
        return report

    return _report


@pytest.fixture
def create_custom_tag(appliance):
    # cannot create a category with uppercase in the name
    category_name = fauxfactory.gen_alphanumeric().lower()
    category = appliance.rest_api.collections.categories.action.create(
        {
            "name": "{cat_name}".format(cat_name=category_name),
            "description": "description_{cat_name}".format(cat_name=category_name),
        }
    )[0]
    assert_response(appliance)

    tag = appliance.rest_api.collections.tags.action.create(
        {
            "name": "{cat_name}_entry".format(cat_name=category_name),
            "description": "{cat_name}_entry_description".format(
                cat_name=category_name
            ),
            "category": {"href": category.href},
        }
    )[0]
    assert_response(appliance)

    yield category_name

    tag.action.delete()
    category.action.delete()


@pytest.fixture(scope="function")
def rbac_api(appliance, request):
    user, user_data = _users(
        request, appliance, password="smartvm", group="EvmGroup-user"
    )
    api = appliance.new_rest_api_instance(
        entry_point=appliance.rest_api._entry_point,
        auth=(user[0].userid, user_data[0]["password"]),
    )
    assert_response(api)
    yield api
    appliance.rest_api.collections.users.action.delete(id=user[0].id)


@test_requirements.rest
@pytest.mark.tier(1)
def test_non_admin_user_reports_access_rest(appliance, request, rbac_api):
    """ This test checks if a non-admin user with proper privileges can access all reports via API.

    Polarion:
        assignee: pvala
        casecomponent: Reporting
        caseimportance: medium
        initialEstimate: 1/12h
        tags: report
        setup:
            1. Create a user with privilege to access reports and REST.
            2. Instantiate a MiqApi instance with the user.
        testSteps:
            1. Access all reports with the new user with the help of newly instantiated API.
        expectedResults:
            1. User should be able to access all reports.
    """
    report_data = rbac_api.collections.reports.all
    assert_response(appliance)
    assert len(report_data)


@pytest.mark.tier(1)
def test_reports_custom_tags(appliance, request, create_custom_tag):
    """
    Polarion:
        assignee: pvala
        casecomponent: Reporting
        caseimportance: low
        initialEstimate: 1/3h
        setup:
            1. Add custom tags to appliance using black console
                i. ssh to appliance, vmdb; rails c
                ii. cat = Classification.create_category!(
                    name: "rocat1", description: "read_only cat 1", read_only: true)
                iii. cat.add_entry(name: "roent1", description: "read_only entry 1")
        testSteps:
            1. Create a new report with the newly created custom tag/category.
        expectedResults:
            1. Report must be created successfully.
    """
    category_name = create_custom_tag
    report_data = {
        "menu_name": "Custom Category Report {}".format(category_name),
        "title": "Custom Category Report Title {}".format(category_name),
        "base_report_on": "Availability Zones",
        "report_fields": [
            "Cloud Manager.My Company Tags : description_{}".format(category_name),
            "VMs.My Company Tags : description_{}".format(category_name),
        ],
    }
    report = appliance.collections.reports.create(**report_data)
    request.addfinalizer(report.delete)
    assert report.exists


@test_requirements.report
@pytest.mark.tier(0)
@pytest.mark.ignore_stream("5.10")
@pytest.mark.parametrize(
    "based_on",
    [
        ("Floating IPs", ["Address", "Status", "Cloud Manager : Name"]),
        (
            "Cloud Tenants",
            ["Name", "My Company Tags : Owner", "My Company Tags : Cost Center"],
        ),
    ],
    ids=["floating_ips", "cloud_tenants"],
)
@pytest.mark.meta(automates=[1546927, 1504155])
def test_new_report_fields(appliance, based_on, request):
    """
    This test case tests report creation with new fields and values.

    Polarion:
        assignee: pvala
        casecomponent: Reporting
        initialEstimate: 1/3h
        testSteps:
            1. Create a report with the parametrized tags.
        expectedResults:
            1. Report should be created successfully.

    Bugzilla:
        1546927
        1504155
    """
    data = {
        "menu_name": "testing report",
        "title": "Testing report",
        "base_report_on": based_on[0],
        "report_fields": based_on[1],
    }
    report = appliance.collections.reports.create(**data)
    request.addfinalizer(report.delete_if_exists)
    assert report.exists


@pytest.mark.tier(1)
@pytest.mark.meta(automates=[1565171, 1519809])
def test_report_edit_secondary_display_filter(
    appliance, request, soft_assert, get_report
):
    """
    Polarion:
        assignee: pvala
        casecomponent: Reporting
        caseimportance: medium
        initialEstimate: 1/6h
        setup:
            1. Create/Copy a report with secondary (display) filter.
        testSteps:
            1. Edit the secondary filter and test if the report was updated.
        expectedResults:
            1. Secondary filter must be editable and it must be updated.

    Bugzilla:
        1565171
        1519809
    """
    report = get_report("filter_report.yaml", "test_filter_report")
    report.update(
        {
            "filter": {
                "primary_filter": (
                    "fill_find("
                    "field=VM and Instance.Guest Applications : Name, skey=STARTS WITH, "
                    "value=env, check=Check Count, ckey= = , cvalue=1"
                    ");select_first_expression;click_or;fill_find("
                    "field=VM and Instance.Guest Applications : Name, skey=STARTS WITH, "
                    "value=kernel, check=Check Count, ckey= = , cvalue=1)"
                ),
                "secondary_filter": (
                    "fill_field(EVM Custom Attributes : Name, INCLUDES, A);"
                    " select_first_expression;click_or;fill_field"
                    "(EVM Custom Attributes : Region Description, INCLUDES, E)"
                ),
            }
        }
    )

    view = report.create_view(ReportDetailsView, wait="10s")

    primary_filter = (
        '( FIND VM and Instance.Guest Applications : Name STARTS WITH "env" CHECK COUNT = 1'
        ' OR FIND VM and Instance.Guest Applications : Name STARTS WITH "kernel" CHECK COUNT = 1 )'
    )
    secondary_filter = (
        '( VM and Instance.EVM Custom Attributes : Name INCLUDES "A"'
        ' OR VM and Instance.EVM Custom Attributes : Region Description INCLUDES "E" )'
    )
    soft_assert(
        view.report_info.primary_filter.read() == primary_filter,
        "Primary Filter did not match.",
    )
    soft_assert(
        view.report_info.secondary_filter.read() == secondary_filter,
        "Secondary Filter did not match.",
    )


@test_requirements.report
@pytest.mark.tier(1)
@pytest.mark.meta(server_roles="+notifier", automates=[1677839])
@pytest.mark.provider([InfraProvider], selector=ONE_PER_CATEGORY)
def test_send_text_custom_report_with_long_condition(
    appliance, setup_provider, smtp_test, request, get_report
):
    """
    Polarion:
        assignee: pvala
        casecomponent: Reporting
        caseimportance: medium
        initialEstimate: 1/3h
        setup:
            1. Create a report containing 1 or 2 columns
                and add a report filter with a long condition.(Refer BZ for more detail)
            2. Create a schedule for the report and check send_txt.
        testSteps:
            1. Queue the schedule and monitor evm log.
        expectedResults:
            1. There should be no error in the log and report must be sent successfully.

    Bugzilla:
        1677839
    """
    report = get_report("long_condition_report.yaml", "test_long_condition_report")
    data = {
        "timer": {"hour": "12", "minute": "10"},
        "email": {"to_emails": "test@example.com"},
        "email_options": {"send_if_empty": True, "send_txt": True},
    }
    schedule = report.create_schedule(**data)
    request.addfinalizer(schedule.delete_if_exists)

    # prepare LogValidator
    log = LogValidator(
        "/var/www/miq/vmdb/log/evm.log", failure_patterns=[".*negative argument.*"]
    )

    log.start_monitoring()
    schedule.queue()

    # assert that the mail was sent
    assert (
        len(smtp_test.wait_for_emails(wait=200, to_address=data["email"]["to_emails"]))
        == 1
    )
    # assert that the pattern was not found in the logs
    assert log.validate(), "Found error message in the logs."
