from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from collections import OrderedDict

class CustomPagination(PageNumberPagination):
    """
    Custom pagination class with configurable page size and additional metadata
    """
    page_size = 10  # Default page size
    page_size_query_param = 'page_size'  # Allow client to override page size
    max_page_size = 100  # Maximum limit on page size
    page_query_param = 'page'  # Query parameter for page number

    def get_paginated_response(self, data):
        """
        Customized pagination response with additional metadata
        """
        return Response(OrderedDict([
            ('count', self.page.paginator.count),  # Total number of items
            ('total_pages', self.page.paginator.num_pages),  # Total number of pages
            ('current_page', self.page.number),  # Current page number
            ('next', self.get_next_link()),  # URL for next page
            ('previous', self.get_previous_link()),  # URL for previous page
            ('page_size', self.get_page_size(self.request)),  # Items per page
            ('results', data)  # Actual data
        ]))

    def get_page_size(self, request):
        """
        Get page size from query parameters or use default
        """
        if self.page_size_query_param:
            try:
                page_size = int(request.query_params.get(
                    self.page_size_query_param, self.page_size
                ))
                return min(page_size, self.max_page_size)
            except (TypeError, ValueError):
                pass
        return self.page_size