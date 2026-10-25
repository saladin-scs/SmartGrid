from functools import partial

from web_sem import views as crud

from .forms import ConsommateurForm, ConsommateurSearchForm

index = partial(crud.individual_list, search_form_class=ConsommateurSearchForm)
detail = partial(crud.individual_detail, form_class=ConsommateurForm)
create = partial(crud.individual_create, form_class=ConsommateurForm)
edit = partial(crud.individual_edit, form_class=ConsommateurForm)
delete = partial(crud.individual_delete, form_class=ConsommateurForm)
