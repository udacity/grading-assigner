import pandas
import pickle
import json
import config
from datetime import datetime, timedelta, date
from tabulate import tabulate
import numpy as np 
import matplotlib
matplotlib.use('Agg')  
import matplotlib.pyplot as plt
from collections import Counter
plt.style.use('ggplot')

"""
This script includes the required functions to generate Reviewer's report.
"""

def count_passed(x):
    '''Small utility to calculate the percent of passed'''
    results = Counter(list(x.values))
    return np.round(100.*results[u'passed']/sum(results.values()),1)

def count_rated(x):
    '''Small utility to calculate the percent of ratings received'''
    results = list(x.values)
    return np.round(100*(x.size - x.isnull().sum())/x.size,1)

def plot_monthly(df,ax,variable,project_colors):
    '''Function to present monthly distributions'''
    monthly_avg_earn = np.round(df.groupby(df.index).sum().loc[:,'earnings'].mean(),1)
    df_test = df.pivot(columns=u'project_name',values=variable)
    color = get_colors(df_test.columns,project_colors)
    if len(color)==1: color = color[0]
    df_test.plot(kind='area', ax=ax, color=color,linewidth=0,xticks=df_test.index)
    handles, labels = ax.get_legend_handles_labels()
    legend = ax.legend(handles[::-1], labels[::-1],loc='center left',bbox_to_anchor=(1, 0.5), prop={'size':8})
    for label in legend.get_lines():
        label.set_linewidth(5)
    ax.set_xlabel('Period')
    ax.set_ylabel(variable)
    ax.set_title('Monthly Results, avg monthly earns: $ {0}'.format(monthly_avg_earn))
    ax.set_xticklabels(df_test.index,rotation='30')
    return ax 
    
def plot_rating(data,ax,period,project_name=None):
    '''Function to represent ratings'''
    ratings = data[[u'created_at',u'rating',u'project']].dropna().sort_values(by=u'created_at',ascending=True).reset_index(drop=True)
    ratings[u'project_name'] =ratings[u'project'].apply(lambda x: x[u'name'],1)  
    ratings[u'created_at'] = pandas.to_datetime(ratings[u'created_at'], format='%Y-%b-%d:%H:%M:%S.%f')
    ratings[u'avg'] = ratings[u'rating'].cumsum() / (ratings.index + 1)
    ratings[u'avg_{0}days'.format(period)] = ratings.apply(lambda row: get_average(ratings,row,period),1)
    
    
    if project_name is not None: 
        ratings = ratings.loc[ratings[u'project_name']== project_name,:].reset_index(drop=True)
        current_avg_period = np.round(ratings.loc[ratings.shape[0]-1,u'avg_30days'],2)
        current_avg = np.round(ratings.loc[ratings.shape[0]-1,u'avg'],2)
        title = 'Project: {3}\nCurrent {0} days average: {1} and full period average: {2}'.format(period,current_avg_period,current_avg,project_name)
        projects = project_name
    else:
        current_avg_period = np.round(ratings.loc[ratings.shape[0]-1,u'avg_30days'],2)
        current_avg = np.round(ratings.loc[ratings.shape[0]-1,u'avg'],2)
        title = 'Current {0} days average: {1} and full period average: {2}'.format(period,current_avg_period,current_avg)
        projects = 'all'
    ratings[[u'created_at',u'avg',u'avg_{0}days'.format(period)]].dropna().set_index(u'created_at').plot(ax=ax)
    ax.set_title(title)
    ax.set_ylabel('Ratings')
    ax.set_xlabel('Date')
    ax.set_ylim(ymax=5.01)
    return ax
    
    
def get_average(data,row,period):
    'Calculate moving average'
    return data.loc[(data[u'created_at']<= row[u'created_at'])&
                    (data[u'created_at']>=row[u'created_at'] - pandas.Timedelta(days=period)),u'rating'].mean()
                    
def get_colors(columns,project_colors):
    '''Function to retrieve the corresponding color for each column'''
    colors = []
    for col in columns:
        colors.append(project_colors[col])
    return colors         
                        
def get_agg_results(df_general,proj_name=None):
    '''Generate different aggregated results from the main dataframe'''
    # Generate new columns:
    df_general.loc[:,u'project_name'] =df_general[u'project'].apply(lambda x: x[u'name'],1)
    if proj_name is not None: df_general = df_general[(df_general[u'project_name'] == proj_name)]
    df_general.loc[:,u'completed_at'] = pandas.to_datetime(df_general[u'completed_at'], format='%Y-%b-%d:%H:%M:%S.%f')
    df_general.loc[:,u'year'] = df_general[u'completed_at'].apply(lambda x: x.year,1)
    df_general.loc[:,u'month'] = df_general[u'completed_at'].apply(lambda x: x.month,1)
    df_general.loc[:,u'%_rated'] = df_general[u'rating']
    df_general.loc[:,u'min_rated'] = df_general[u'rating']
    df_general.loc[:,u'max_rated'] = df_general[u'rating']
    df_general.loc[:,u'%_passed'] = df_general[u'result']
    df_general = df_general.groupby([u'project_name',
                             u'year',
                             u'month'],as_index=False).agg({u'project':'count',
                                                             u'rating':'mean',
                                                             u'max_rated':'max',
                                                             u'min_rated':'min',
                                                             u'%_rated':count_rated,
                                                             u'%_passed':count_passed,
                                                             u'price':'sum'
                                                             }).sort_values(by=[u'project_name',u'year',u'month'])
    
    df_general.rename(columns={u'price':u'earnings',u'project':u'count'},inplace=True)
    df_general.loc[:,u'date_time']= df_general.apply(lambda row :date(row.year,row.month,1),axis=1)
    df_general.set_index(u'date_time',inplace=True)
    
    ## Generate grouped results:
    df_results = pandas.DataFrame(columns=['Distinct Projects Reviewed','Count','Earns($)','Avg Rating','Avg Passed'])
    df_results.loc[1,:] = [df_general[u'project_name'].nunique(),df_general[u'count'].sum(),
                           df_general[u'earnings'].sum(),np.round(df_general[u'rating'].mean(),2),
                           np.round(df_general[u'%_passed'].mean(),1)]
    
    ## Generate project results:
    df_projects = df_general.drop([u'year',u'month'],axis=1).groupby(u'project_name',as_index=False).agg({u'rating':'mean',
                                                                                             u'max_rated':'max',
                                                                                             u'min_rated':'min',
                                                                                             u'%_rated':'mean',
                                                                                             u'%_passed':'mean',
                                                                                             u'earnings':'sum'
                                                                                             }).sort_values(by=[u'earnings'],ascending=False)
    return df_general, df_results, df_projects

#################################################################
## Generate dataframe to calculate General results:
#################################################################
def generate_report(df_all):
    '''Generate general numbers and visualizations'''
    df_general, df_results, df_projects = get_agg_results(df_all.copy())
    
    ## Assign colors to projects:
    cmap = matplotlib.cm.get_cmap('Paired')
    colors = np.linspace(0.0, 1.0, num=df_projects[u'project_name'].nunique())
    project_colors = dict([(projname,cmap(color)) for projname,color in zip(df_projects[u'project_name'].unique(),colors)])
    
    # Calculate general results:
    start_date = df_general.index.min()
    end_date = df_general.index.max()
    summary_table = tabulate([list(row) for row in df_results.round(2).values], headers=list(df_results.columns),tablefmt="pipe", numalign="center")
    fig, axes = plt.subplots(nrows=2, ncols=1)
    axes[0] = plot_monthly(df_general,axes[0],u'earnings',project_colors)
    axes[1] = plot_rating(df_all.copy(),axes[1],period)
    monthly_plot_path = config.path_out + 'general.png'
    plt.tight_layout()
    fig.savefig(monthly_plot_path, bbox_inches='tight')
    plt.close()
    
    monthly_table = tabulate([list(row) for row in df_projects.round(2).values], headers=list(df_projects.columns),tablefmt="pipe", numalign="center")
    
    file_text = general_text_body.format(start_date,end_date,summary_table,monthly_plot_path,monthly_table)
    project_names = df_projects['project_name'].unique()
    return file_text,project_names,project_colors

#################################################################
# Generate project results:
#################################################################
def generate_project_report(df_all,project_names,project_colors,file_text):
    '''Generate general numbers and visualizations for the different projects'''
    for project_name in project_names:
        proj_results,proj_summary,_ = get_agg_results(df_all,proj_name=project_name)
        proj_summary = tabulate([list(row) for row in proj_summary.iloc[:,1:].round(2).values], headers=list(proj_summary.iloc[:,1:].columns),tablefmt="pipe", numalign="center")
        proj_table = tabulate([list(row) for row in proj_results.round(2).values], headers=list(proj_results.columns),tablefmt="pipe", numalign="center")
        fig, axes = plt.subplots(nrows=2, ncols=1)
        axes[0] = plot_monthly(proj_results,axes[0],u'earnings',project_colors)
        axes[1] = plot_rating(df_all.copy(),axes[1],period,project_name=project_name)
        project_plot_path = config.path_out + '{0}.png'.format(project_name)
        plt.tight_layout()
        fig.savefig(project_plot_path, bbox_inches='tight')
        plt.close()
        file_text +=  project_text_body.format(project_name,proj_summary,proj_table,project_plot_path)
    return file_text

#################################################################
## Markdown Sections:
#################################################################
    
general_text_body = """
# Reviewer Performance Report
In this report it is summarized reviewer's performance for the period: {0} - {1}. Following table presents most aggregated numbers:\n

{2}
<br />
Following visualizations show monthly earnings per project and ratings:

![monthly_visualizations]({3})
<br />
Summary results for each project:\n

{4}
<br /><br />
  
  
"""

project_text_body = """
#### {0} Project Summary:

Summary stats:\n
{1}<br />
Following table shows monthly results:\n
{2}
<br />
Visualizations with the earns and ratings by month:
![project_visualizations]({3})
<br /><br />
"""

project_text_foot = """
<br /><br />
Want more? Open an issue in the [GitHub repo](https://github.com/kingkastle/grading-assigner/tree/project_selection) or contact kingkastle4004@gmail.com or do it yourself, we all want to benefit from your work too :smile:
<br /><br />
"""                

#################################################################
## Configuration:
#################################################################
period = 30 # Period to calculate moving window in average rating




