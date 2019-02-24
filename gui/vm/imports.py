from django.utils.translation import ugettext_lazy as _
from logging import getLogger
import csv
import time

from gui.excel import Excel
from gui.vm.utils import ImportExportBase


logger = getLogger(__name__)


class ImportException(Exception):
    pass


# noinspection PyUnusedLocal
def process_ods(import_file):
    # TODO: Move to class same way as excel is done
    # doc = ODSReader(import_file)
    # table = doc.getSheet('Sheet1')
    # firstRow = table[0]
    # firstCellOfFirstRow = firstRow[0]

    # return header, vm_list
    return None


def process_csv(import_file):
    # TODO: Move to class same way as excel is done
    vm_list = iter(csv.reader(import_file))  # Nice!
    header = vm_list.next()

    ieb = ImportExportBase()

    if not ieb.check_header(header):
        raise ImportException(ieb.HEADER_ERROR)

    return header, vm_list


def handle_uploaded_file(import_file, request):
    logger.info('Uploaded file: %s', import_file)
    logger.info('File content type is: %s', import_file.content_type)
    if import_file.content_type == 'text/csv':
        return process_csv(import_file)

    elif import_file.content_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' \
            or import_file.content_type == 'application/vnd.ms-excel' \
            or import_file.content_type == 'application/vms.ms-excel' \
            or import_file.content_type == 'application/msexcel':

        imp = Import(request, filename=import_file)
        return imp.process_file()

    elif import_file.content_type == 'application/vnd.oasis.opendocument.spreadsheet':
        return process_ods(import_file)

    else:
        raise ImportException(_('Uploaded file mimetype: "%s" has not been recognized!') % import_file.content_type)


class Import(ImportExportBase, Excel):

    request = None
    rows = None
    columns_no = None

    def __init__(self, request, filename):
        super(Import, self).__init__()

        self.request = request
        # Load Workbook
        self.load_workbook(filename=filename)
        self.sheet_dc = self.wb.get_sheet_by_name(self.sheet_dc_name)

        self.verify_header()

    def verify_header(self):
        """
        Function that will parse imported file and collect header and verify if it meets our expectations
        :return: boolean
        """
        header = []
        if self.sheet_dc is None:
            raise ImportException(self.sheet_dc_name + ' sheet has not been found')

        self.rows = self.sheet_dc.iter_rows()
        self.rows.next()  # First row in XLS (Total Row, we don't care what is here)

        for idx, field in enumerate(self.rows.next()):  # Second row in XLS (Header row, collect it)
            if field.value is not None:
                header.append(field.value)
            else:
                # In some cases library reads whole excel (thousands cells)
                # so we collect header until we find empty cell
                logger.warn('Detected empty space at column %s, last column in file is %s.' % (self.get_letter(idx + 1),
                            self.sheet_dc.max_col))  # idx starts from 0 and excel from 1
                break

        if not self.check_header(header):
            raise ImportException(self.HEADER_ERROR)

        self.columns_no = len(header)

        return True

    def process_file(self):
        html_table = dict()

        file_process_timer = time.time()
        # Pre define variables required for import and html generation
        vm = self.get_empty_vm()
        html_rows = []
        last_letter = self.get_letter(self.columns_no)

        logger.info('File cells to be processed: A3:%s%s' % (last_letter, self.sheet_dc.max_row))

        xls_id = 0
        for idx, row in enumerate(self.rows):  # Rest of the rows in XLS (all data rows)
            # idx start from 0 and work sheet from 1, there are 2 header lines on the top of the file
            # current line number in excel is idx + 3 and next line is idx + 4
            xls_id = idx + 3

            # Check for the marker of END of the file. Row index 0 is column A in XLS
            if row[0].value == 'END':
                logger.info('Row no. %s has END file marker, we don\'t process file further...' % xls_id)
                break
            # Check for empty row, which means END of the file
            if not any([cell.value for cell in row[:self.columns_no]]):
                logger.warn('Row no. %s was empty in the file, we don\'t process file further...' % xls_id)
                break

            row_process_timer = time.time()
            try:
                next_row = next(self.sheet_dc.iter_rows('A%s:%s%s' % (xls_id + 1, last_letter, xls_id + 1)))
            except StopIteration:
                vm, html_row = self.process_row(vm, row, False)
            else:
                vm, html_row = self.process_row(vm, row, next_row)

            logger.debug('Row A%s:%s%s has been processed in %ss' % (xls_id, last_letter, xls_id,
                         time.time() - row_process_timer))
            html_rows.append(html_row)

            if vm['complete']:
                html_table[vm['hostname']] = {
                    'json': vm['json'],
                    'html_rows': html_rows
                }
                vm = self.get_empty_vm()
                html_rows = []

        logger.info('File has been processed in %ss. Total processed rows: %s' % (time.time() - file_process_timer,
                                                                                  xls_id))
        return html_table
