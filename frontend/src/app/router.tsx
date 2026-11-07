import React from 'react';
import { Navigate, Route, Routes } from 'react-router';
import { Layout } from './Layout';
import { NewAnalysisPage } from '../features/new-analysis/NewAnalysisPage';
import { AnalysisShell } from '../features/analysis/AnalysisShell';
import { OverviewTab } from '../features/analysis/OverviewTab';
import { ResearchTab } from '../features/research/ResearchTab';
import { HistoryPage } from '../features/history/HistoryPage';
import { DevUiPage } from '../components/ui/DevUiPage';
import * as PrecedentsModule from '../features/precedents/PrecedentsTab';
import * as ScenariosModule from '../features/scenarios/ScenariosTab';
import * as AssumptionsModule from '../features/assumptions/AssumptionsTab';
import * as VerificationModule from '../features/verification/VerificationTab';
import * as ReportModule from '../features/report/ReportTab';
import * as EvaluationModule from '../features/evaluation/EvaluationPage';

const PrecedentsTab: React.ComponentType =
  PrecedentsModule.PrecedentsTab ?? PrecedentsModule.default;
const ScenariosTab: React.ComponentType =
  ScenariosModule.ScenariosTab ?? ScenariosModule.default;
const AssumptionsTab: React.ComponentType =
  AssumptionsModule.AssumptionsTab ?? AssumptionsModule.default;
const VerificationTab: React.ComponentType =
  VerificationModule.VerificationTab ?? VerificationModule.default;
const ReportTab: React.ComponentType =
  ReportModule.ReportTab ?? ReportModule.default;
const EvaluationPage: React.ComponentType =
  EvaluationModule.EvaluationPage ?? EvaluationModule.default;

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<NewAnalysisPage />} />
        <Route path="/analyses/:id" element={<AnalysisShell />}>
          <Route index element={<Navigate to="overview" replace />} />
          <Route path="overview" element={<OverviewTab />} />
          <Route path="research" element={<ResearchTab />} />
          <Route path="precedents" element={<PrecedentsTab />} />
          <Route path="scenarios" element={<ScenariosTab />} />
          <Route path="assumptions" element={<AssumptionsTab />} />
          <Route path="verification" element={<VerificationTab />} />
          <Route path="report" element={<ReportTab />} />
        </Route>
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/evaluation" element={<EvaluationPage />} />
        <Route path="/dev/ui" element={<DevUiPage />} />
      </Route>
    </Routes>
  );
}

export default AppRoutes;
