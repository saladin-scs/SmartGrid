from web_sem.forms import IndividualForm, IndividualSearchForm


class InfrastructureForm(IndividualForm):
    module_root = "Infrastructure"


class InfrastructureSearchForm(IndividualSearchForm):
    module_root = "Infrastructure"