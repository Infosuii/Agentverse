"""Documented announcement transcription; rates themselves come from HMRC.

Each tuple is (announcement date, fiscal event, source document key).
1983 and 1990 changes are retrospective; effective dates must not be moved.
"""
DOCUMENTS = {
    'budget1984.html': ('https://hansard.parliament.uk/Commons/1984-03-13/debates/6cf4b7c6-4a55-429a-a8a9-e7617b155785/CommonsChamber', 'Budget speech 13 March 1984: corporation tax and capital allowances', 'Parliament', 'parliament'),
    'budget1991.html': ('https://hansard.parliament.uk/commons/1991-03-19/debates/37cfce8d-a615-420f-a132-917ccf219ef4/CommonsChamber', 'Budget speech 19 March 1991: corporation tax', 'Parliament', 'parliament'),
    'budget1997.html': ('https://hansard.parliament.uk/Commons/1997-07-02/debates/25efc1ce-0352-4c6a-b353-def04ca4c618/CommonsChamber', 'Budget speech 2 July 1997: corporation tax', 'Parliament', 'parliament'),
    'budget1998.html': ('https://hansard.parliament.uk/commons/1998-03-17/debates/b52b11d8-562f-4016-b28b-110f2f11b404/CommonsChamber', 'Budget speech 17 March 1998: corporation tax and ACT', 'Parliament', 'parliament'),
    'budget2007.html': ('https://hansard.parliament.uk/Commons/2007-03-21/debates/d71fcb9d-858f-4a83-a532-3c88bb72b8be/CommonsChamber', 'Budget speech 21 March 2007: business tax reform', 'Parliament', 'parliament'),
    'budget2011.html': ('https://www.gov.uk/government/news/2011-budget-britain-open-for-business', '2011 Budget: Britain open for business, 23 March 2011', 'HM Treasury', 'hmt'),
    'budget2012.pdf': ('https://assets.publishing.service.gov.uk/media/5a7c923ced915d6969f45d0b/1853.pdf', 'Budget 2012, 21 March: Table 2.1 corporation tax package', 'HM Treasury', 'hmt'),
    'autumn2012.html': ('https://www.gov.uk/government/news/autumn-statement-2012-an-overview', 'Autumn Statement 2012 overview, 5 December', 'HM Treasury', 'hmt'),
    'budget2013.html': ('https://www.gov.uk/government/speeches/budget-2013-chancellors-statement', 'Budget speech 20 March 2013: corporation tax unification', 'HM Treasury', 'hmt'),
    'budget2015.html': ('https://www.gov.uk/government/publications/summer-budget-2015/summer-budget-2015', 'Summer Budget 8 July 2015: corporation tax package', 'HM Treasury', 'hmt'),
    'budget2016.html': ('https://www.gov.uk/government/publications/budget-2016-documents/budget-2016', 'Budget 16 March 2016: planned corporation tax rate reduction', 'HM Treasury', 'hmt'),
    'budget2021.html': ('https://www.gov.uk/government/publications/budget-2021-documents/budget-2021-html', 'Budget 3 March 2021: Table 2.1 row 22', 'HM Treasury', 'hmt'),
    'reversal2020.html': ('https://www.gov.uk/government/publications/changes-to-corporation-tax-rates-from-1-april-2020/corporation-tax-main-rate-at-19-in-2020-and-charge-and-main-rate-for-2021', 'HMRC March 2020: reversal of 2016-announced 17 percent rate', 'HMRC', 'hmrc'),
    'full_expensing.html': ('https://www.gov.uk/government/publications/capital-allowances-full-expensing/capital-allowances-full-expensing-for-companies-investing-in-plant-and-machinery-from-1-april-2023-until-31-march-2026', 'HMRC 15 March 2023: introduction of full expensing', 'HMRC', 'hmrc'),
}

EVENTS = {y: ('1984-03-13', 'Budget 1984', 'budget1984.html') for y in range(1983, 1987)}
EVENTS.update({y: ('1991-03-19', 'Budget 1991', 'budget1991.html') for y in (1990, 1991)})
EVENTS.update({
    1997: ('1997-07-02', 'Budget 1997', 'budget1997.html'),
    1999: ('1998-03-17', 'Budget 1998', 'budget1998.html'),
    2008: ('2007-03-21', 'Budget 2007', 'budget2007.html'),
    2011: ('2011-03-23', 'Budget 2011', 'budget2011.html'),
    2012: ('2012-03-21', 'Budget 2012', 'budget2012.pdf'),
    2013: ('2012-03-21', 'Budget 2012', 'budget2012.pdf'),
    2014: ('2012-12-05', 'Autumn Statement 2012', 'autumn2012.html'),
    2015: ('2013-03-20', 'Budget 2013', 'budget2013.html'),
    2017: ('2015-07-08', 'Summer Budget 2015', 'budget2015.html'),
    2023: ('2021-03-03', 'Spring Budget 2021', 'budget2021.html'),
})


def source_id(filename):
    return 'D-' + filename.split('.')[0]
