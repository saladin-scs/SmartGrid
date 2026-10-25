from functools import partial

from web_sem import views as crud

from .forms import PersonneForm, PersonneSearchForm

index = partial(crud.individual_list, search_form_class=PersonneSearchForm)
detail = partial(crud.individual_detail, form_class=PersonneForm)
create = partial(crud.individual_create, form_class=PersonneForm)
edit = partial(crud.individual_edit, form_class=PersonneForm)
delete = partial(crud.individual_delete, form_class=PersonneForm)
