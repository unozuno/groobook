from io import BytesIO
import openpyxl
from openpyxl.styles import Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter


def _build_baebonapyo_excel(
    workbook, outlist1, outlist2, publishers, campuses,
    main_banding, mini_banding, teacher_banding
) -> bytes:
    """원본 workbook에 배본표 시트 3개(본책/미니북/교사용)를 추가하고 bytes 반환."""
    green_fill = PatternFill(start_color="00B100", end_color="00B100", fill_type="solid")
    yellow_fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    center = Alignment(horizontal='center', vertical='center')

    title_prefix = workbook.worksheets[0].title[-3:]
    # 총 열 수: A, B + 캠퍼스당 2열 + 합계 2열
    last_col = 2 + 2 * (len(campuses) + 1)

    def _make_sheet(sheet_name, data_matrix, banding, col_header):
        sheet = workbook.create_sheet(sheet_name)
        # 시트명에서 타입 이름 추출 (예: "고사 본책 배본표" → "본책")
        type_name = sheet_name.replace(title_prefix, '').strip().replace(' 배본표', '')

        # 1행: 병합 제목
        sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_col)
        sheet['A1'] = f'{title_prefix} {type_name} 분원별 배본표'

        # 2행: A2:A3 병합="no", B2:B3 병합="제품명", 캠퍼스 2열씩 병합, 합계 병합
        sheet.merge_cells('A2:A3')
        sheet.cell(row=2, column=1, value='no')
        sheet.merge_cells('B2:B3')
        sheet.cell(row=2, column=2, value='제품명')
        sheet.column_dimensions['A'].width = 4.5
        sheet.column_dimensions['B'].width = 13

        col_idx = 3
        for campus in campuses:
            sheet.merge_cells(start_row=2, start_column=col_idx, end_row=2, end_column=col_idx + 1)
            sheet.cell(row=2, column=col_idx, value=campus)
            col_idx += 2
        # 합계 헤더
        sheet.merge_cells(start_row=2, start_column=col_idx, end_row=2, end_column=col_idx + 1)
        sheet.cell(row=2, column=col_idx, value='합계')

        # 3행: col_header + 덩이수 반복 (캠퍼스 수 + 합계 1개)
        col_idx = 3
        for _ in range(len(campuses) + 1):
            sheet.cell(row=3, column=col_idx, value=col_header)
            sheet.cell(row=3, column=col_idx + 1, value='덩이수')
            col_idx += 2

        # 출판사 목록 입력 (A열: 번호, B열: 이름)
        for pub_idx, pub_name in enumerate(publishers):
            row = 4 + pub_idx
            sheet.cell(row=row, column=1, value=pub_idx + 1)
            sheet.cell(row=row, column=2, value=pub_name)

        # 데이터 입력
        total_list = [0] * (2 * (len(campuses) + 1))
        for pub_idx, data_row in enumerate(data_matrix):
            row = 4 + pub_idx
            sum_stu = 0
            sum_pack = 0
            for cam_idx, quantity in enumerate(data_row):
                col = 3 + cam_idx * 2
                result = quantity // banding + (1 if quantity % banding != 0 else 0)
                sheet.cell(row=row, column=col, value=quantity)
                sheet.cell(row=row, column=col + 1, value=result)
                sum_stu += quantity
                sum_pack += result
                total_list[cam_idx * 2] += quantity
                total_list[cam_idx * 2 + 1] += result
            # 합계 열 입력
            sum_col = 3 + len(campuses) * 2
            sheet.cell(row=row, column=sum_col, value=sum_stu)
            sheet.cell(row=row, column=sum_col + 1, value=sum_pack)
            total_list[len(campuses) * 2] += sum_stu
            total_list[len(campuses) * 2 + 1] += sum_pack

        # 소계 행
        total_row = 4 + len(publishers)
        sheet.merge_cells(start_row=total_row, start_column=1, end_row=total_row, end_column=2)
        sheet.cell(row=total_row, column=1, value='소계')
        for i, val in enumerate(total_list):
            sheet.cell(row=total_row, column=3 + i, value=val)

        # 색상: 2행 초록
        for i in range(1, last_col + 1):
            sheet.cell(row=2, column=i).fill = green_fill
        # 색상: col_header / 덩이수 셀 노란
        for row_cells in sheet.iter_rows(min_row=3, max_row=sheet.max_row):
            for cell in row_cells:
                if str(cell.value) in (col_header, '덩이수'):
                    cell.fill = yellow_fill

        # 전체 가운데 정렬 + 테두리
        for row_cells in sheet.iter_rows():
            for cell in row_cells:
                cell.alignment = center
                cell.border = thin_border

    _make_sheet(f'{title_prefix} 본책 배본표', outlist2, main_banding, '학생용')
    _make_sheet(f'{title_prefix} 미니북 배본표', outlist2, mini_banding, '학생용')
    _make_sheet(f'{title_prefix} 교사용 배본표', outlist1, teacher_banding, '교사용')

    buf = BytesIO()
    workbook.save(buf)
    return buf.getvalue()


def process_midterm(
    file_bytes: bytes,
    main_banding: int = 20,
    mini_banding: int = 70,
    teacher_banding: int = 15,
    progress_cb=None,
) -> list:
    """
    중간기말교재 Excel 분석 → slip list 반환

    중간기말교재 구조:
    - 책(출판사)이 열(가로)에 위치
    - 캠퍼스가 행(세로)에 위치
    - 짝수행 = TR(교사용) 수량, 홀수행 = 전체; 학생용 = 전체 - TR

    slip 구조 (8요소):
    [캠퍼스, 학년+시험명, "N번", 출판사, "N부", 총덩이수, "-", 현재번호]
    정렬: 본책 전체 → 미니북 전체 → 교사용 전체
          각 타입 내: 책 열 인덱스 오름차순 → 캠퍼스 행 인덱스 오름차순
    """
    def cb(pct, msg):
        if progress_cb:
            progress_cb(pct, msg)

    cb(10, "파일 읽는 중...")
    workbook = openpyxl.load_workbook(BytesIO(file_bytes))
    sheet1 = workbook.worksheets[0]

    cb(25, "데이터 추출 중...")

    # A2: 학년 + 시험 정보
    cell_value = sheet1['A2'].value
    words = cell_value.split()
    quarter_info = " ".join(words[1:3])
    grade = " ".join(words[-1:])

    # Row 3 (C열~"계"전): 출판사 목록
    publishers = []
    for cell in sheet1[3][2:-1]:
        if cell.value == "계":
            break
        else:
            publishers.append(cell.value)

    # A열 (row 4~, 2행씩, "총계" 전): 캠퍼스 목록
    campuses = []
    row_number = 4
    while True:
        cell_value = sheet1.cell(row=row_number, column=1).value
        if str(cell_value)[-2:] == "총계":
            break
        campuses.append(cell_value)
        row_number += 2

    # 마지막 열("계" 열) 찾기
    last_column = None
    for col in range(1, sheet1.max_column + 1):
        if sheet1.cell(row=3, column=col).value == "계":
            last_column = col
            break

    cb(40, "수량 분리 중...")

    # outlist1: TR(교사용) 수량 [출판사][캠퍼스]
    # outlist2: 학생용 수량 = 전체 - TR [출판사][캠퍼스]
    outlist1 = []
    outlist2 = []

    for col in range(3, last_column):
        inlist1 = []  # TR (짝수행)
        inlist2 = []  # 전체 (홀수행)
        row = 4
        for _ in range(4, 4 + 2 * len(campuses)):
            cell_value = sheet1.cell(row=row, column=col).value
            if type(cell_value) != int:
                break
            if row % 2 == 0:
                inlist1.append(cell_value)
            else:
                inlist2.append(cell_value)
            row += 1

        if len(inlist1) != 0:
            outlist1.append(inlist1)
        if len(inlist2) != 0:
            # 학생용 = 전체 - TR
            inlist3 = [inlist2[k] - inlist1[k] for k in range(len(campuses))]
            outlist2.append(inlist3)

    cb(55, "포장 계산 중...")

    def make_slips(data_matrix, banding, type_label):
        """
        data_matrix: [책 index][캠퍼스 index] → 수량
        slip 구조 (6섹션 레이아웃):
        [캠퍼스이름, 학년+타입, 캠퍼스인덱스(1부터), 출판사, 부수, 총덩이수, "-", 현재번호]
        """
        slips = []
        for pub_idx, data_row in enumerate(data_matrix):
            pub_name = publishers[pub_idx]
            pub_num = pub_idx + 1  # 출판사 인덱스 1부터 시작
            for cam_idx, quantity in enumerate(data_row):
                campus = campuses[cam_idx]
                if not quantity or quantity == 0:
                    continue
                packing = quantity // banding + (1 if quantity % banding != 0 else 0)
                remaining = quantity
                for counter in range(1, packing + 1):
                    qty_str = f"{banding}부" if remaining - banding > 0 else f"{remaining}부"
                    slips.append([campus, f"{grade} {type_label}", pub_num, pub_name, qty_str, packing, "-", counter])
                    if remaining - banding > 0:
                        remaining -= banding
        return slips

    # 본책 → 미니북 → 교사용 순서
    slip_list = []
    slip_list.extend(make_slips(outlist2, main_banding, "본책"))
    slip_list.extend(make_slips(outlist2, mini_banding, "미니북"))
    slip_list.extend(make_slips(outlist1, teacher_banding, "교사용"))

    cb(75, "배본표 생성 중...")
    excel_bytes = _build_baebonapyo_excel(
        workbook, outlist1, outlist2, publishers, campuses,
        main_banding, mini_banding, teacher_banding
    )
    workbook.close()
    return slip_list, excel_bytes
