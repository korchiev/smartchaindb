#!/usr/bin/env python3
"""
Enhanced Metrics Analysis Tool

This tool analyzes the enhanced metrics data to compare SHACL vs traditional validation performance.
"""

import json
import csv
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import argparse
import os
from typing import Dict, List, Any
import numpy as np

class MetricsAnalyzer:
    """Analyzes enhanced metrics data for SHACL vs traditional validation comparison"""
    
    def __init__(self, csv_file: str = "enhanced-metrics.csv"):
        self.csv_file = csv_file
        self.df = None
        self.load_data()
    
    def load_data(self):
        """Load metrics data from CSV"""
        if not os.path.exists(self.csv_file):
            print(f"Metrics file {self.csv_file} not found. Run some transactions first.")
            return
        
        self.df = pd.read_csv(self.csv_file)
        print(f"Loaded {len(self.df)} transaction records")
    
    def generate_summary_report(self) -> Dict[str, Any]:
        """Generate comprehensive summary report"""
        if self.df is None or len(self.df) == 0:
            return {"error": "No data available"}
        
        # Basic statistics
        total_txs = len(self.df)
        shacl_txs = len(self.df[self.df['validation_type'] == 'SHACL'])
        traditional_txs = len(self.df[self.df['validation_type'] == 'TRADITIONAL'])
        
        # Performance metrics
        shacl_data = self.df[self.df['validation_type'] == 'SHACL']
        traditional_data = self.df[self.df['validation_type'] == 'TRADITIONAL']
        
        report = {
            'overview': {
                'total_transactions': total_txs,
                'shacl_transactions': shacl_txs,
                'traditional_transactions': traditional_txs,
                'shacl_percentage': (shacl_txs / total_txs * 100) if total_txs > 0 else 0
            },
            'latency_comparison': self._compare_latency(shacl_data, traditional_data),
            'validation_performance': self._compare_validation_performance(shacl_data, traditional_data),
            'operation_breakdown': self._analyze_by_operation(),
            'error_analysis': self._analyze_errors(),
            'shacl_phase_analysis': self._analyze_shacl_phases(shacl_data),
            'traditional_component_analysis': self._analyze_traditional_components(traditional_data)
        }
        
        return report
    
    def _compare_latency(self, shacl_data: pd.DataFrame, traditional_data: pd.DataFrame) -> Dict[str, Any]:
        """Compare latency metrics between SHACL and traditional validation"""
        comparison = {}
        
        if len(shacl_data) > 0:
            comparison['shacl'] = {
                'avg_total_latency_ms': shacl_data['total_latency_ms'].mean(),
                'median_total_latency_ms': shacl_data['total_latency_ms'].median(),
                'p95_total_latency_ms': shacl_data['total_latency_ms'].quantile(0.95),
                'p99_total_latency_ms': shacl_data['total_latency_ms'].quantile(0.99),
                'min_total_latency_ms': shacl_data['total_latency_ms'].min(),
                'max_total_latency_ms': shacl_data['total_latency_ms'].max(),
                'std_total_latency_ms': shacl_data['total_latency_ms'].std()
            }
        
        if len(traditional_data) > 0:
            comparison['traditional'] = {
                'avg_total_latency_ms': traditional_data['total_latency_ms'].mean(),
                'median_total_latency_ms': traditional_data['total_latency_ms'].median(),
                'p95_total_latency_ms': traditional_data['total_latency_ms'].quantile(0.95),
                'p99_total_latency_ms': traditional_data['total_latency_ms'].quantile(0.99),
                'min_total_latency_ms': traditional_data['total_latency_ms'].min(),
                'max_total_latency_ms': traditional_data['total_latency_ms'].max(),
                'std_total_latency_ms': traditional_data['total_latency_ms'].std()
            }
        
        # Calculate performance difference
        if len(shacl_data) > 0 and len(traditional_data) > 0:
            shacl_avg = comparison['shacl']['avg_total_latency_ms']
            traditional_avg = comparison['traditional']['avg_total_latency_ms']
            
            comparison['performance_difference'] = {
                'shacl_vs_traditional_ms': shacl_avg - traditional_avg,
                'shacl_vs_traditional_percent': ((shacl_avg - traditional_avg) / traditional_avg * 100) if traditional_avg > 0 else 0,
                'faster_method': 'SHACL' if shacl_avg < traditional_avg else 'TRADITIONAL'
            }
        
        return comparison
    
    def _compare_validation_performance(self, shacl_data: pd.DataFrame, traditional_data: pd.DataFrame) -> Dict[str, Any]:
        """Compare validation-specific performance metrics"""
        comparison = {}
        
        if len(shacl_data) > 0:
            comparison['shacl'] = {
                'avg_validation_time_ms': shacl_data['validation_duration_ms'].mean(),
                'median_validation_time_ms': shacl_data['validation_duration_ms'].median(),
                'success_rate': (shacl_data['validation_success'].sum() / len(shacl_data)) * 100,
                'avg_tendermint_overhead_ms': shacl_data['tendermint_overhead_ms'].mean()
            }
        
        if len(traditional_data) > 0:
            comparison['traditional'] = {
                'avg_validation_time_ms': traditional_data['validation_duration_ms'].mean(),
                'median_validation_time_ms': traditional_data['validation_duration_ms'].median(),
                'success_rate': (traditional_data['validation_success'].sum() / len(traditional_data)) * 100,
                'avg_tendermint_overhead_ms': traditional_data['tendermint_overhead_ms'].mean()
            }
        
        return comparison
    
    def _analyze_by_operation(self) -> Dict[str, Any]:
        """Analyze performance by transaction operation type"""
        operation_analysis = {}
        
        for operation in self.df['operation'].unique():
            op_data = self.df[self.df['operation'] == operation]
            shacl_op = op_data[op_data['validation_type'] == 'SHACL']
            traditional_op = op_data[op_data['validation_type'] == 'TRADITIONAL']
            
            operation_analysis[operation] = {
                'total_count': len(op_data),
                'shacl_count': len(shacl_op),
                'traditional_count': len(traditional_op),
                'shacl_avg_latency_ms': shacl_op['total_latency_ms'].mean() if len(shacl_op) > 0 else None,
                'traditional_avg_latency_ms': traditional_op['total_latency_ms'].mean() if len(traditional_op) > 0 else None,
                'shacl_avg_validation_ms': shacl_op['validation_duration_ms'].mean() if len(shacl_op) > 0 else None,
                'traditional_avg_validation_ms': traditional_op['validation_duration_ms'].mean() if len(traditional_op) > 0 else None
            }
        
        return operation_analysis
    
    def _analyze_errors(self) -> Dict[str, Any]:
        """Analyze validation errors and failures"""
        error_analysis = {
            'total_failures': len(self.df[self.df['validation_success'] == False]),
            'shacl_failures': len(self.df[(self.df['validation_type'] == 'SHACL') & (self.df['validation_success'] == False)]),
            'traditional_failures': len(self.df[(self.df['validation_type'] == 'TRADITIONAL') & (self.df['validation_success'] == False)]),
            'failure_rate_by_type': {},
            'failure_rate_by_operation': {}
        }
        
        # Failure rate by validation type
        shacl_total = len(self.df[self.df['validation_type'] == 'SHACL'])
        traditional_total = len(self.df[self.df['validation_type'] == 'TRADITIONAL'])
        
        if shacl_total > 0:
            error_analysis['failure_rate_by_type']['SHACL'] = (error_analysis['shacl_failures'] / shacl_total) * 100
        
        if traditional_total > 0:
            error_analysis['failure_rate_by_type']['TRADITIONAL'] = (error_analysis['traditional_failures'] / traditional_total) * 100
        
        # Failure rate by operation
        for operation in self.df['operation'].unique():
            op_data = self.df[self.df['operation'] == operation]
            failures = len(op_data[op_data['validation_success'] == False])
            error_analysis['failure_rate_by_operation'][operation] = (failures / len(op_data)) * 100
        
        return error_analysis
    
    def _analyze_shacl_phases(self, shacl_data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze SHACL validation phases"""
        if len(shacl_data) == 0:
            return {}
        
        phase_analysis = {
            'phase1_stats': {
                'avg_time_ms': shacl_data['shacl_phase1_time_ms'].mean(),
                'median_time_ms': shacl_data['shacl_phase1_time_ms'].median(),
                'p95_time_ms': shacl_data['shacl_phase1_time_ms'].quantile(0.95)
            },
            'phase2_stats': {
                'avg_time_ms': shacl_data['shacl_phase2_time_ms'].mean(),
                'median_time_ms': shacl_data['shacl_phase2_time_ms'].median(),
                'p95_time_ms': shacl_data['shacl_phase2_time_ms'].quantile(0.95)
            },
            'phase_comparison': {
                'phase1_vs_phase2_ratio': shacl_data['shacl_phase1_time_ms'].mean() / shacl_data['shacl_phase2_time_ms'].mean() if shacl_data['shacl_phase2_time_ms'].mean() > 0 else 0,
                'phase1_percentage': (shacl_data['shacl_phase1_time_ms'].mean() / shacl_data['shacl_total_time_ms'].mean()) * 100 if shacl_data['shacl_total_time_ms'].mean() > 0 else 0,
                'phase2_percentage': (shacl_data['shacl_phase2_time_ms'].mean() / shacl_data['shacl_total_time_ms'].mean()) * 100 if shacl_data['shacl_total_time_ms'].mean() > 0 else 0
            }
        }
        
        return phase_analysis
    
    def _analyze_traditional_components(self, traditional_data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze traditional validation components"""
        if len(traditional_data) == 0:
            return {}
        
        component_analysis = {
            'schema_validation': {
                'avg_time_ms': traditional_data['schema_validation_time_ms'].mean(),
                'median_time_ms': traditional_data['schema_validation_time_ms'].median()
            },
            'business_logic': {
                'avg_time_ms': traditional_data['business_logic_time_ms'].mean(),
                'median_time_ms': traditional_data['business_logic_time_ms'].median()
            },
            'signature_validation': {
                'avg_time_ms': traditional_data['signature_validation_time_ms'].mean(),
                'median_time_ms': traditional_data['signature_validation_time_ms'].median()
            },
            'component_breakdown': {}
        }
        
        # Calculate percentage breakdown
        total_avg = traditional_data['traditional_validation_time_ms'].mean()
        if total_avg > 0:
            component_analysis['component_breakdown'] = {
                'schema_percentage': (component_analysis['schema_validation']['avg_time_ms'] / total_avg) * 100,
                'business_logic_percentage': (component_analysis['business_logic']['avg_time_ms'] / total_avg) * 100,
                'signature_percentage': (component_analysis['signature_validation']['avg_time_ms'] / total_avg) * 100
            }
        
        return component_analysis
    
    def generate_visualizations(self, output_dir: str = "metrics_plots"):
        """Generate visualization plots"""
        if self.df is None or len(self.df) == 0:
            print("No data available for visualization")
            return
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Set style
        plt.style.use('seaborn-v0_8')
        
        # 1. Latency comparison
        self._plot_latency_comparison(output_dir)
        
        # 2. Validation time comparison
        self._plot_validation_time_comparison(output_dir)
        
        # 3. Operation breakdown
        self._plot_operation_breakdown(output_dir)
        
        # 4. SHACL phase analysis
        self._plot_shacl_phases(output_dir)
        
        # 5. Traditional component analysis
        self._plot_traditional_components(output_dir)
        
        # 6. Error rate comparison
        self._plot_error_rates(output_dir)
        
        print(f"Visualizations saved to {output_dir}/")
    
    def _plot_latency_comparison(self, output_dir: str):
        """Plot latency comparison between SHACL and traditional validation"""
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Latency Comparison: SHACL vs Traditional Validation', fontsize=16)
        
        # Total latency box plot
        self.df.boxplot(column='total_latency_ms', by='validation_type', ax=axes[0,0])
        axes[0,0].set_title('Total Latency Distribution')
        axes[0,0].set_ylabel('Latency (ms)')
        
        # Validation time box plot
        self.df.boxplot(column='validation_duration_ms', by='validation_type', ax=axes[0,1])
        axes[0,1].set_title('Validation Time Distribution')
        axes[0,1].set_ylabel('Time (ms)')
        
        # Tendermint overhead
        self.df.boxplot(column='tendermint_overhead_ms', by='validation_type', ax=axes[1,0])
        axes[1,0].set_title('Tendermint Overhead')
        axes[1,0].set_ylabel('Time (ms)')
        
        # Latency over time
        for validation_type in self.df['validation_type'].unique():
            data = self.df[self.df['validation_type'] == validation_type]
            axes[1,1].plot(data.index, data['total_latency_ms'], 
                          label=validation_type, alpha=0.7, marker='o', markersize=2)
        axes[1,1].set_title('Latency Over Time')
        axes[1,1].set_xlabel('Transaction Index')
        axes[1,1].set_ylabel('Latency (ms)')
        axes[1,1].legend()
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/latency_comparison.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    def _plot_validation_time_comparison(self, output_dir: str):
        """Plot validation time comparison"""
        fig, axes = plt.subplots(1, 2, figsize=(15, 6))
        fig.suptitle('Validation Time Analysis', fontsize=16)
        
        # Validation time histogram
        for validation_type in self.df['validation_type'].unique():
            data = self.df[self.df['validation_type'] == validation_type]['validation_duration_ms']
            axes[0].hist(data, alpha=0.7, label=validation_type, bins=30)
        axes[0].set_title('Validation Time Distribution')
        axes[0].set_xlabel('Time (ms)')
        axes[0].set_ylabel('Frequency')
        axes[0].legend()
        
        # Average validation time by operation
        operation_avg = self.df.groupby(['operation', 'validation_type'])['validation_duration_ms'].mean().unstack()
        operation_avg.plot(kind='bar', ax=axes[1])
        axes[1].set_title('Average Validation Time by Operation')
        axes[1].set_xlabel('Operation')
        axes[1].set_ylabel('Time (ms)')
        axes[1].legend(title='Validation Type')
        axes[1].tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/validation_time_analysis.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    def _plot_operation_breakdown(self, output_dir: str):
        """Plot performance breakdown by operation"""
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Performance by Operation Type', fontsize=16)
        
        # Transaction count by operation
        operation_counts = self.df.groupby(['operation', 'validation_type']).size().unstack(fill_value=0)
        operation_counts.plot(kind='bar', ax=axes[0,0])
        axes[0,0].set_title('Transaction Count by Operation')
        axes[0,0].set_ylabel('Count')
        axes[0,0].legend(title='Validation Type')
        axes[0,0].tick_params(axis='x', rotation=45)
        
        # Average latency by operation
        operation_latency = self.df.groupby(['operation', 'validation_type'])['total_latency_ms'].mean().unstack()
        operation_latency.plot(kind='bar', ax=axes[0,1])
        axes[0,1].set_title('Average Latency by Operation')
        axes[0,1].set_ylabel('Latency (ms)')
        axes[0,1].legend(title='Validation Type')
        axes[0,1].tick_params(axis='x', rotation=45)
        
        # Success rate by operation
        success_rate = self.df.groupby(['operation', 'validation_type'])['validation_success'].mean().unstack()
        success_rate.plot(kind='bar', ax=axes[1,0])
        axes[1,0].set_title('Success Rate by Operation')
        axes[1,0].set_ylabel('Success Rate')
        axes[1,0].legend(title='Validation Type')
        axes[1,0].tick_params(axis='x', rotation=45)
        
        # Performance difference heatmap
        if len(operation_latency.columns) == 2:
            performance_diff = operation_latency.iloc[:, 0] - operation_latency.iloc[:, 1]
            performance_diff.plot(kind='bar', ax=axes[1,1], color=['red' if x > 0 else 'green' for x in performance_diff])
            axes[1,1].set_title('Performance Difference (SHACL - Traditional)')
            axes[1,1].set_ylabel('Latency Difference (ms)')
            axes[1,1].tick_params(axis='x', rotation=45)
            axes[1,1].axhline(y=0, color='black', linestyle='--', alpha=0.5)
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/operation_breakdown.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    def _plot_shacl_phases(self, output_dir: str):
        """Plot SHACL phase analysis"""
        shacl_data = self.df[self.df['validation_type'] == 'SHACL']
        if len(shacl_data) == 0:
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('SHACL Validation Phase Analysis', fontsize=16)
        
        # Phase time distribution
        axes[0,0].hist(shacl_data['shacl_phase1_time_ms'].dropna(), alpha=0.7, label='Phase 1', bins=20)
        axes[0,0].hist(shacl_data['shacl_phase2_time_ms'].dropna(), alpha=0.7, label='Phase 2', bins=20)
        axes[0,0].set_title('Phase Time Distribution')
        axes[0,0].set_xlabel('Time (ms)')
        axes[0,0].set_ylabel('Frequency')
        axes[0,0].legend()
        
        # Phase comparison scatter
        axes[0,1].scatter(shacl_data['shacl_phase1_time_ms'], shacl_data['shacl_phase2_time_ms'], alpha=0.6)
        axes[0,1].set_title('Phase 1 vs Phase 2 Time')
        axes[0,1].set_xlabel('Phase 1 Time (ms)')
        axes[0,1].set_ylabel('Phase 2 Time (ms)')
        
        # Phase percentage pie chart
        phase1_avg = shacl_data['shacl_phase1_time_ms'].mean()
        phase2_avg = shacl_data['shacl_phase2_time_ms'].mean()
        axes[1,0].pie([phase1_avg, phase2_avg], labels=['Phase 1', 'Phase 2'], autopct='%1.1f%%')
        axes[1,0].set_title('Average Time Distribution')
        
        # Phase time over transactions
        axes[1,1].plot(shacl_data.index, shacl_data['shacl_phase1_time_ms'], label='Phase 1', alpha=0.7)
        axes[1,1].plot(shacl_data.index, shacl_data['shacl_phase2_time_ms'], label='Phase 2', alpha=0.7)
        axes[1,1].set_title('Phase Time Over Transactions')
        axes[1,1].set_xlabel('Transaction Index')
        axes[1,1].set_ylabel('Time (ms)')
        axes[1,1].legend()
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/shacl_phase_analysis.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    def _plot_traditional_components(self, output_dir: str):
        """Plot traditional validation component analysis"""
        traditional_data = self.df[self.df['validation_type'] == 'TRADITIONAL']
        if len(traditional_data) == 0:
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Traditional Validation Component Analysis', fontsize=16)
        
        # Component time distribution
        components = ['schema_validation_time_ms', 'business_logic_time_ms', 'signature_validation_time_ms']
        for i, component in enumerate(components):
            axes[0,0].hist(traditional_data[component].dropna(), alpha=0.7, label=component.replace('_time_ms', ''), bins=20)
        axes[0,0].set_title('Component Time Distribution')
        axes[0,0].set_xlabel('Time (ms)')
        axes[0,0].set_ylabel('Frequency')
        axes[0,0].legend()
        
        # Component percentage pie chart
        component_avgs = [traditional_data[comp].mean() for comp in components]
        component_labels = [comp.replace('_time_ms', '').replace('_', ' ').title() for comp in components]
        axes[0,1].pie(component_avgs, labels=component_labels, autopct='%1.1f%%')
        axes[0,1].set_title('Average Time Distribution')
        
        # Component time over transactions
        for component in components:
            axes[1,0].plot(traditional_data.index, traditional_data[component], 
                          label=component.replace('_time_ms', ''), alpha=0.7)
        axes[1,0].set_title('Component Time Over Transactions')
        axes[1,0].set_xlabel('Transaction Index')
        axes[1,0].set_ylabel('Time (ms)')
        axes[1,0].legend()
        
        # Component comparison box plot
        component_data = [traditional_data[comp].dropna() for comp in components]
        axes[1,1].boxplot(component_data, labels=component_labels)
        axes[1,1].set_title('Component Time Comparison')
        axes[1,1].set_ylabel('Time (ms)')
        axes[1,1].tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/traditional_component_analysis.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    def _plot_error_rates(self, output_dir: str):
        """Plot error rate analysis"""
        fig, axes = plt.subplots(1, 2, figsize=(15, 6))
        fig.suptitle('Error Rate Analysis', fontsize=16)
        
        # Error rate by validation type
        error_by_type = self.df.groupby('validation_type')['validation_success'].apply(lambda x: (x == False).sum() / len(x) * 100)
        error_by_type.plot(kind='bar', ax=axes[0])
        axes[0].set_title('Error Rate by Validation Type')
        axes[0].set_ylabel('Error Rate (%)')
        axes[0].tick_params(axis='x', rotation=0)
        
        # Error rate by operation
        error_by_operation = self.df.groupby(['operation', 'validation_type'])['validation_success'].apply(lambda x: (x == False).sum() / len(x) * 100).unstack()
        error_by_operation.plot(kind='bar', ax=axes[1])
        axes[1].set_title('Error Rate by Operation')
        axes[1].set_ylabel('Error Rate (%)')
        axes[1].legend(title='Validation Type')
        axes[1].tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/error_rate_analysis.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    def print_summary_report(self):
        """Print a formatted summary report"""
        report = self.generate_summary_report()
        
        if 'error' in report:
            print(f"Error: {report['error']}")
            return
        
        print("=" * 80)
        print("ENHANCED METRICS ANALYSIS REPORT")
        print("=" * 80)
        
        # Overview
        print(f"\n📊 OVERVIEW:")
        print(f"   Total Transactions: {report['overview']['total_transactions']}")
        print(f"   SHACL Transactions: {report['overview']['shacl_transactions']} ({report['overview']['shacl_percentage']:.1f}%)")
        print(f"   Traditional Transactions: {report['overview']['traditional_transactions']}")
        
        # Latency comparison
        if 'latency_comparison' in report and 'performance_difference' in report['latency_comparison']:
            diff = report['latency_comparison']['performance_difference']
            print(f"\n⚡ LATENCY COMPARISON:")
            print(f"   SHACL Average Latency: {report['latency_comparison']['shacl']['avg_total_latency_ms']:.2f} ms")
            print(f"   Traditional Average Latency: {report['latency_comparison']['traditional']['avg_total_latency_ms']:.2f} ms")
            print(f"   Performance Difference: {diff['shacl_vs_traditional_ms']:.2f} ms ({diff['shacl_vs_traditional_percent']:.1f}%)")
            print(f"   Faster Method: {diff['faster_method']}")
        
        # Validation performance
        print(f"\n🔍 VALIDATION PERFORMANCE:")
        if 'shacl' in report['validation_performance']:
            shacl_perf = report['validation_performance']['shacl']
            print(f"   SHACL Validation Time: {shacl_perf['avg_validation_time_ms']:.2f} ms")
            print(f"   SHACL Success Rate: {shacl_perf['success_rate']:.1f}%")
        
        if 'traditional' in report['validation_performance']:
            trad_perf = report['validation_performance']['traditional']
            print(f"   Traditional Validation Time: {trad_perf['avg_validation_time_ms']:.2f} ms")
            print(f"   Traditional Success Rate: {trad_perf['success_rate']:.1f}%")
        
        # Error analysis
        print(f"\n❌ ERROR ANALYSIS:")
        error_analysis = report['error_analysis']
        print(f"   Total Failures: {error_analysis['total_failures']}")
        print(f"   SHACL Failures: {error_analysis['shacl_failures']}")
        print(f"   Traditional Failures: {error_analysis['traditional_failures']}")
        
        if 'failure_rate_by_type' in error_analysis:
            for validation_type, rate in error_analysis['failure_rate_by_type'].items():
                print(f"   {validation_type} Failure Rate: {rate:.1f}%")
        
        # SHACL phase analysis
        if 'shacl_phase_analysis' in report and report['shacl_phase_analysis']:
            phase_analysis = report['shacl_phase_analysis']
            print(f"\n🔬 SHACL PHASE ANALYSIS:")
            print(f"   Phase 1 Average Time: {phase_analysis['phase1_stats']['avg_time_ms']:.2f} ms")
            print(f"   Phase 2 Average Time: {phase_analysis['phase2_stats']['avg_time_ms']:.2f} ms")
            print(f"   Phase 1 Percentage: {phase_analysis['phase_comparison']['phase1_percentage']:.1f}%")
            print(f"   Phase 2 Percentage: {phase_analysis['phase_comparison']['phase2_percentage']:.1f}%")
        
        print("\n" + "=" * 80)

def main():
    """Main function for command-line usage"""
    parser = argparse.ArgumentParser(description='Analyze enhanced metrics data')
    parser.add_argument('--csv', default='enhanced-metrics.csv', help='CSV file with metrics data')
    parser.add_argument('--plots', action='store_true', help='Generate visualization plots')
    parser.add_argument('--output-dir', default='metrics_plots', help='Output directory for plots')
    
    args = parser.parse_args()
    
    analyzer = MetricsAnalyzer(args.csv)
    
    # Print summary report
    analyzer.print_summary_report()
    
    # Generate plots if requested
    if args.plots:
        analyzer.generate_visualizations(args.output_dir)

if __name__ == "__main__":
    main()
