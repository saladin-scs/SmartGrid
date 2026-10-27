from web_sem.forms import IndividualForm, IndividualSearchForm, PropertyField


class ConsommateurForm(IndividualForm):
    module_root = "Consommateur"
    property_fields = (
        PropertyField(
            "souscritContrat",
            "Contrat souscrit",
            kind="ref",
            ref_root="Contrat",
            ref_class="ContratAbonnement",
            help_text="Contrat associé à ce consommateur.",
        ),
    )


class ConsommateurSearchForm(IndividualSearchForm):
    module_root = "Consommateur"
