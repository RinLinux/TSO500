
import os
import sys
sub=os.path.abspath(__file__)
dir_name=os.path.dirname(sub)
sys.path.append(dir_name)
import core
import argparse
import configparser
import subprocess
import re

class Myconf(configparser.ConfigParser):
    def __init__(self, defaults=None):
        configparser.ConfigParser.__init__(self, defaults=defaults)
    def optionxform(self, optionstr):
        return optionstr


def run_docker(pe1,pe2,outdir,prefix,indexID,configfile):
    ###########################################
    config = Myconf()
    config.read(configfile)
    TSO500 = config.read('software', 'TSO500')
    infile=open("%s/resources/sampleSheet/TSO500_NovaSeq_Sample_Sheet_Template.csv","r")
    index, index2="",""
    for line in infile:
        line=line.strip()
        array=line.split(",")
        if array[4]==indexID:
            index=array[5]
            index2=array[6]
    infile.close()
    ##########step1:print samplesheet############
    outfile=open("%s/SampleSheet.csv"%(outdir),"w")
    outfile.write("""
    [Header],,,,,,,
IEMFileVersion,4,,,,,,
Investigator Name,User Name,,,,,,
Experiment Name,Experiment,,,,,,
Date,2019/12/1,,,,,,
Workflow,GenerateFASTQ,,,,,,
Application,NovaSeq,,,,,,
Assay,,,,,,,
Description,,,,,,,
Chemistry,Default,,,,,,
,,,,,,,
[Reads],,,,,,,
101,,,,,,,
101,,,,,,,
,,,,,,,
[Settings],,,,,,,
AdapterRead1,AGATCGGAAGAGCACACGTCTGAACTCCAGTCA,,,,,,
AdapterRead2,AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT,,,,,,
AdapterBehavior,trim,,,,,,
MinimumTrimmedReadLength,35,,,,,,
MaskShortReads,35,,,,,,
OverrideCycles,U7N1Y93;I8;I8;U7N1Y93,,,,,,
,,,,,,,
[Data],,,,,,,,
Sample_ID,Sample_Name,Sample_Plate,Sample_Well,Index_ID,index,index2,Sample_Type,Pair_ID
%s,,,,%s,%s,%s,DNA,%s\n
    """%(prefix,indexID,index,index2,prefix))
    outfile.close()
    #####################change the fastq name################
    if not os.path.exists("%s/analysis/docker_run.log"%(outdir)):
        subprocess.check_call("rm -rf %s/analysis/"%(outdir),shell=True)
        os.makedirs("%s/fastq/"%(outdir))
        subprocess.check_call("cp %s %s/fastq/%s_S1_L001_R1_001.fastq.gz"%(pe1,outdir,prefix),shell=True)
        subprocess.check_call("cp %s %s/fastq/%s_S1_L001_R2_001.fastq.gz" % (pe2, outdir, prefix), shell=True)
        cmd = "cd %s && %s --resourcesFolder %s/resources --fastqFolder %s/fastq/ --analysisFolder %s/analysis/ --sampleSheet %s/SampleSheet.csv" % (
        os.path.dirname(TSO500), TSO500, os.path.dirname(TSO500), outdir, outdir, outdir)
        subprocess.check_call(cmd, shell=True)
        subprocess.check_call("echo done >%s/analysis/docker_run.log" % (outdir), shell=True)

def run(indir,project_name,configfile):
    config = Myconf()
    config.read(configfile)
    outdir=indir+"/final_result"
    ID=[]
    if not os.path.exists(outdir):
        os.makedirs(outdir)
        os.makedirs("%s/CNV"%(outdir))
        os.makedirs("%s/SNV_indel" % (outdir))
        os.makedirs("%s/TMB_MSI" % (outdir))
    for(root,dirs,files) in os.walk(indir):
        for file in files:
            tmp=os.path.join(root,file)
            sample = tmp.split("/")[-2]
            if tmp.endswith("CopyNumberVariants.vcf"):
                ID.append(sample)
                print(tmp)
                core.format_CNV.run(tmp,"%s/CNV"%(outdir),sample)
            elif tmp.endswith("TMB_Trace.tsv"):
                print(tmp)
                gvcf=tmp.replace("TMB_Trace.tsv","MergedSmallVariants.genome.vcf")
                core.format_SNV_indel.run(tmp,gvcf,"%s/SNV_indel"%(outdir),sample)
                core.anno_vcf.run("%s/SNV_indel/%s.vcf"%(outdir,sample),"%s/SNV_indel"%(outdir),sample,configfile)
                subprocess.check_call("rm -rf %s/SNV_indel/%s.vcf"%(outdir,sample),shell=True)
            elif tmp.split("/")[-3]=="StitchedRealigned" and tmp.endswith("bam"):
                print(tmp)
                core.copy_file.run(project_name,tmp)
                core.copy_file.run(project_name,"%s.bai"%(tmp))
            elif tmp.split("/")[-1]=="MetricsOutput.tsv":
                print(tmp)
                subprocess.check_call("cp %s -rf %s"%(tmp,outdir),shell=True)
            elif tmp.endswith("CombinedVariantOutput.tsv"):
                print(tmp)
                subprocess.check_call("cp %s -rf %s/TMB_MSI"%(tmp,outdir),shell=True)
            else:
                pass
    subprocess.check_call("cd %s && tar -zcvf final_result.tar.gz final_result/"%(indir),shell=True)
    core.copy_file.run(project_name,"%s/final_result.tar.gz"%(indir))

if __name__=="__main__":
    parer=argparse.ArgumentParser()
    parer.add_argument("-p1","--pe1",help="5 reads",required=True)
    parer.add_argument("-p2", "--pe2", help="3 reads", required=True)
    parer.add_argument("-o","--outdir",help="output directory",required=True)
    parer.add_argument("-p","--prefix",help="prefix of output",required=True)
    parer.add_argument("-n","--name",help="project name",required=True)
    parer.add_argument("-c","--config",help="config file",required=True)
    parer.add_argument("-i","--indexID",help="index id",required=True)
    args=parer.parse_args()
    run_docker(args.pe1, args.pe2, args.outdir, args.prefix, args.indexID, args.config)
    run("%s/analysis"%(args.outdir), args.name, args.config)