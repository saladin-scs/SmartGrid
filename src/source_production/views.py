from functools import partial

from web_sem import views as crud

from .forms import SourceProductionForm, SourceProductionSearchForm

index = partial(crud.individual_list, search_form_class=SourceProductionSearchForm)
detail = partial(crud.individual_detail, form_class=SourceProductionForm)
create = partial(crud.individual_create, form_class=SourceProductionForm)
edit = partial(crud.individual_edit, form_class=SourceProductionForm)
delete = partial(crud.individual_delete, form_class=SourceProductionForm)
