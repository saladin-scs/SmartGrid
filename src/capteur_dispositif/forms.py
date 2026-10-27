from web_sem.forms import IndividualForm, IndividualSearchForm, PropertyField


class CapteurDispositifForm(IndividualForm):
    module_root = "CapteurDispositif"
    property_fields = (
        PropertyField(
            "declenche",
            "Événement déclenché",
            kind="ref",
            ref_root="Evenement",
            help_text="Événement déclenché par ce capteur ou dispositif.",
        ),
    )


class CapteurDispositifSearchForm(IndividualSearchForm):
    module_root = "CapteurDispositif"
