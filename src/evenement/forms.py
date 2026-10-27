from web_sem.forms import IndividualForm, IndividualSearchForm, PropertyField


class EvenementForm(IndividualForm):
    module_root = "Evenement"
    property_fields = (
        PropertyField(
            "dateEvenement",
            "Date de l’événement",
            kind="date",
            help_text="Date de survenue ou date planifiée (AAAA-MM-JJ).",
        ),
        PropertyField(
            "concerne",
            "Infrastructure concernée",
            kind="ref",
            ref_root="Infrastructure",
            only_classes=("Maintenance",),
            help_text="Réservé aux opérations de maintenance.",
        ),
    )


class EvenementSearchForm(IndividualSearchForm):
    module_root = "Evenement"
