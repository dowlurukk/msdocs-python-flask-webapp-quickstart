from paperscraper.pubmed import get_pubmed_papers, dump_papers
import os
import pandas as pd

class PubmedApi :
    def get_guideline_urls(self, guidelines_query):
        papers = get_pubmed_papers(guidelines_query)
        paper_list = list(papers.T.to_dict().values())
        print(paper_list)
        return paper_list

