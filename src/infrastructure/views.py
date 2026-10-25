from functools import partial

from web_sem import views as crud

from .forms import InfrastructureForm, InfrastructureSearchForm

index = partial(crud.individual_list, search_form_class=InfrastructureSearchForm)
detail = partial(crud.individual_detail, form_class=InfrastructureForm)
create = partial(crud.individual_create, form_class=InfrastructureForm)
edit = partial(crud.individual_edit, form_class=InfrastructureForm)
delete = partial(crud.individual_delete, form_class=InfrastructureForm)