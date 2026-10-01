from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.pagination import PageNumberPagination


class OfferPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_page_size(self, request):
        value = request.query_params.get(self.page_size_query_param)
        if value is None:
            return self.page_size

        try:
            page_size = int(value)
        except (TypeError, ValueError):
            raise ValidationError({"page_size": "Must be a positive integer."})

        if not 1 <= page_size <= self.max_page_size:
            raise ValidationError(
                {"page_size": f"Must be between 1 and {self.max_page_size}."}
            )
        return page_size

    def paginate_queryset(self, queryset, request, view=None):
        try:
            return super().paginate_queryset(queryset, request, view)
        except NotFound as error:
            raise ValidationError({"page": str(error.detail)})