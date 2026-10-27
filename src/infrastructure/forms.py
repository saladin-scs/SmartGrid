from web_sem.forms import IndividualForm, IndividualSearchForm, PropertyField


class InfrastructureForm(IndividualForm):
    module_root = "Infrastructure"
    property_fields = (
        PropertyField(
            "estSitueDans",
            "Située dans la zone",
            kind="ref",
            ref_root="Zone",
            help_text="Zone géographique de cette infrastructure.",
        ),
    )


class InfrastructureSearchForm(IndividualSearchForm):
    module_root = "Infrastructure"