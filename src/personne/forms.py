from web_sem.forms import IndividualForm, IndividualSearchForm


class PersonneForm(IndividualForm):
    module_root = "Personne"


class PersonneSearchForm(IndividualSearchForm):
    module_root = "Personne"
