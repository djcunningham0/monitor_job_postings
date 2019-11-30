import os.path
import utils


class JobList:
    """
    This class contains methods used to report changes to job postings for any company. A subclass with a 'scrape'
    method defined should be created for each website that will be scraped.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) \
        Chrome/59.0.3071.115 Safari/537.36"}
    headers["User-Agent"] += "; contact info: djcunningham0@gmail.com"

    folder = "./job_list_files/"

    sender = "djcunningham0@gmail.com"
    to = "djcunningham0@gmail.com"

    # some defaults (can be overridden by subclass)
    report_adds = True
    report_deletes = True
    print_report = True
    email_report = True

    def __init__(self, url, careers_link, filename, company_name, scrape):
        self.url = url
        self.soup = utils.get_soup(url=url, headers=self.headers)
        self.careers_link = careers_link
        self.filepath = utils.format_csv_filepath(os.path.join(self.folder, filename))
        self.company_name = company_name
        self.scrape = scrape
        self.subject = company_name + " job postings"

    def run(self):
        """
        Scrape data and report any changes.
        """
        if self.soup is not None:
            jobs, jobs_html, colnames = self.scrape()

            # look for differences between URL and CSV and report them (print and/or email)
            if os.path.isfile(self.filepath):
                self.report_changes(jobs, jobs_html, colnames)

            # update the CSV file
            utils.write_csv(self.filepath, jobs, colnames)

    def report_changes(self, data, data_html, colnames):
        """
        Determine if any jobs have been added or removed since the last check. Report additions or deletions
        by print report or email as specified.

        :param data: jobs data returned from self.scrape()
        :param data_html: jobs HTML data returned from self.scrape()
        :param colnames: column names of jobs data
        """
        adds, adds_html, deletes = utils.find_adds_deletes(filepath=self.filepath, data=data, data_html=data_html,
                                                           colnames=colnames)

        # set these to None in case they don't get defined later
        adds_table, adds_table_html, deletes_table, deletes_table_html = None, None, None, None

        # print the added and deleted jobs if print_report == True
        if adds:
            adds_table = utils.create_text_table(adds, colnames)
            adds_table_html = utils.create_html_table(adds_html, colnames)
            if self.print_report and self.report_adds:
                utils.print_table(adds_table, company_name=self.company_name, message_start="New jobs posted")

        if deletes:
            deletes_table = utils.create_text_table(deletes, colnames)
            deletes_table_html = utils.create_html_table(deletes, colnames)  # don't need links deletes table
            if self.print_report and self.report_deletes:
                utils.print_table(deletes_table, company_name=self.company_name, message_start="Jobs removed")

        # if there were changes that need reporting and email_report == True, send an email
        needs_report = ((self.report_adds and adds) or (self.report_deletes and deletes))
        if self.email_report and needs_report:
            service = utils.establish_service()

            # build the message text
            email_adds = False
            email_deletes = False

            if self.report_adds and adds:
                email_adds = True

            if self.report_deletes and deletes:
                email_deletes = True

            text_msg, html_msg = utils.build_message(adds_table, adds_table_html, deletes_table, deletes_table_html,
                                                     self.company_name, email_adds, email_deletes)

            # include link to careers page at bottom of email if available
            if (self.careers_link is not None) and (self.careers_link != ""):
                html_msg += '\n<p></p>\n<p>Careers page: <a href="' + self.careers_link + '">' + self.careers_link + \
                            '</a></p>\n'
                text_msg += '\n\nCareers page: ' + self.careers_link + '\n'

            # create and send message using Gmail API
            msg = utils.create_message(self.sender, self.to, self.subject, text_msg, html_msg)
            utils.send_message(service, user_id="me", message=msg)


class StatsLLC(JobList):
    """
    Job scraper for STATS
    """
    def __init__(self, only_chicago=True,
                 report_adds=True, report_deletes=True, print_report=True, email_report=True):

        super().__init__(url="https://recruit.hirebridge.com/v3/jobs/list.aspx?cid=7082&m=0",
                         careers_link="https://www.statsperform.com/stats-careers/",
                         filename="stats_llc.csv",
                         company_name="STATS",
                         scrape=self.scrape)

        self.only_chicago = only_chicago
        self.report_adds = report_adds
        self.report_deletes = report_deletes
        self.print_report = print_report
        self.email_report = email_report

    def scrape(self):
        """
        Scrape the STATS job website.

        :return: job data, job data with HTML formatting, and column names for job data
        """
        sections = self.soup.find_all('section')
        jobs = []
        jobs_html = []

        for section in sections:
            # find only Chicago jobs if specified; otherwise look in all locations
            if (not self.only_chicago) or section.find('h2', text="US-IL-Chicago"):
                location = section.find('h2').text
                for job in section.find_all('ul', class_="jobs"):
                    title = job.find('span', class_="job").text.strip()
                    dep = job.find('span', class_="department").text.strip()
                    jobs.append([title, dep, location])

                    # also grab the link so we can put it in the HTML table
                    link = job.find('span', class_='job').find('a')['href']
                    link = "https://www.hirebridge.com" + link
                    title_link = '<a href="' + link + '">' + title + '</a>'
                    jobs_html.append([title_link, dep, location])

        colnames = ["Job", "Department", "Location"]

        return jobs, jobs_html, colnames


# run the report
if __name__ == '__main__':
    stats = StatsLLC(print_report=False)
    stats.run()
