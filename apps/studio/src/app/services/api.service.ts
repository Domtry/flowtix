import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Process, ProcessVersion, Execution, ExecutionStep } from '../models/process.model';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private baseUrl = '/api/v1';

  constructor(private http: HttpClient) {}

  private authHeaders(): HttpHeaders {
    const token = localStorage.getItem('flowtix_token');
    return token ? new HttpHeaders({ Authorization: `Bearer ${token}` }) : new HttpHeaders();
  }

  // Processes
  getProcesses(): Observable<Process[]> {
    return this.http.get<Process[]>(`${this.baseUrl}/processes`);
  }

  getProcess(id: string): Observable<Process> {
    return this.http.get<Process>(`${this.baseUrl}/processes/${id}`);
  }

  createProcess(name: string, description?: string, robotCode?: string): Observable<Process> {
    return this.http.post<Process>(`${this.baseUrl}/processes`, { name, description, robot_code: robotCode || undefined });
  }

  updateProcess(id: string, data: { name?: string; description?: string; robot_code?: string }): Observable<Process> {
    return this.http.put<Process>(`${this.baseUrl}/processes/${id}`, data);
  }

  deleteProcess(id: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/processes/${id}`);
  }

  // Versions
  getVersions(processId: string): Observable<ProcessVersion[]> {
    return this.http.get<ProcessVersion[]>(`${this.baseUrl}/processes/${processId}/versions`);
  }

  createVersion(processId: string, definition: any): Observable<ProcessVersion> {
    return this.http.post<ProcessVersion>(
      `${this.baseUrl}/processes/${processId}/versions`,
      { definition }
    );
  }

  updateVersion(processId: string, versionId: string, data: { definition?: any; status?: string }): Observable<ProcessVersion> {
    return this.http.put<ProcessVersion>(
      `${this.baseUrl}/processes/${processId}/versions/${versionId}`,
      data
    );
  }

  deleteVersion(processId: string, versionId: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/processes/${processId}/versions/${versionId}`);
  }

  // Executions
  createExecution(processId: string, versionId: string, inputs?: any): Observable<Execution> {
    return this.http.post<Execution>(
      `${this.baseUrl}/processes/${processId}/executions`,
      { version_id: versionId, inputs }
    );
  }

  getExecutions(processId: string): Observable<Execution[]> {
    return this.http.get<Execution[]>(`${this.baseUrl}/processes/${processId}/executions`);
  }

  getExecution(executionId: string): Observable<Execution> {
    return this.http.get<Execution>(`${this.baseUrl}/executions/${executionId}`);
  }

  getExecutionSteps(executionId: string): Observable<ExecutionStep[]> {
    return this.http.get<ExecutionStep[]>(`${this.baseUrl}/executions/${executionId}/steps`);
  }

  // Recording
  startRecording(processId: string, targetUrl: string, opts?: { browserPath?: string; actionType?: string; engine?: string; windowTitlePattern?: string; keepSession?: boolean }): Observable<any> {
    return this.http.post(`${this.baseUrl}/recording/start`, {
      process_id: processId,
      target_url: targetUrl,
      browser_path: opts?.browserPath || undefined,
      action_type: opts?.actionType || 'web',
      engine: opts?.engine || 'auto',
      window_title_pattern: opts?.windowTitlePattern || '',
      keep_session: !!opts?.keepSession,
    });
  }

  stopRecording(sessionId: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/recording/${sessionId}/stop`, {});
  }

  getRecordingEvents(sessionId: string): Observable<any[]> {
    return this.http.get<any[]>(`${this.baseUrl}/recording/${sessionId}/events`);
  }

  // Execution control
  startExecution(executionId: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/executions/${executionId}/start`, {});
  }

  pauseExecution(executionId: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/executions/${executionId}/pause`, {});
  }

  resumeExecution(executionId: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/executions/${executionId}/resume`, {});
  }

  cancelExecution(executionId: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/executions/${executionId}/cancel`, {});
  }

  getExecutionState(executionId: string): Observable<any> {
    return this.http.get(`${this.baseUrl}/executions/${executionId}/state`);
  }

  // Auth
  login(email: string, password: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/users/login`, { email, password });
  }

  register(email: string, name: string, password: string, role = 'operator'): Observable<any> {
    return this.http.post(`${this.baseUrl}/users/register`, { email, name, password, role });
  }

  getMe(): Observable<any> {
    return this.http.get(`${this.baseUrl}/users/me`, { headers: this.authHeaders() });
  }

  // Settings
  getSettings(): Observable<any[]> {
    return this.http.get<any[]>(`${this.baseUrl}/settings/`);
  }

  getSetting(key: string): Observable<any> {
    return this.http.get(`${this.baseUrl}/settings/${key}`);
  }

  saveSetting(key: string, value: string): Observable<any> {
    return this.http.put(`${this.baseUrl}/settings/${key}`, { value });
  }

  // App Modules
  getAppModules(): Observable<any[]> {
    return this.http.get<any[]>(`${this.baseUrl}/app-modules/`);
  }

  createAppModule(module: any): Observable<any> {
    return this.http.post(`${this.baseUrl}/app-modules/`, module);
  }

  updateAppModule(code: string, data: any): Observable<any> {
    return this.http.put(`${this.baseUrl}/app-modules/${code}`, data);
  }

  deleteAppModule(code: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/app-modules/${code}`);
  }

  // Robots
  getRobots(): Observable<any[]> {
    return this.http.get<any[]>(`${this.baseUrl}/robots/`);
  }

  getRobot(code: string): Observable<any> {
    return this.http.get(`${this.baseUrl}/robots/${code}`);
  }

  createRobot(robot: any): Observable<any> {
    return this.http.post(`${this.baseUrl}/robots/`, robot);
  }

  updateRobot(code: string, data: any): Observable<any> {
    return this.http.put(`${this.baseUrl}/robots/${code}`, data);
  }

  deleteRobot(code: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/robots/${code}`);
  }

  // Pipelines
  getPipelines(): Observable<any[]> {
    return this.http.get<any[]>(`${this.baseUrl}/pipelines`);
  }

  getPipeline(id: string): Observable<any> {
    return this.http.get(`${this.baseUrl}/pipelines/${id}`);
  }

  createPipeline(data: { name: string; description?: string; robot_code?: string }): Observable<any> {
    return this.http.post(`${this.baseUrl}/pipelines`, data);
  }

  updatePipeline(id: string, data: { name?: string; description?: string; robot_code?: string; graph?: any }): Observable<any> {
    return this.http.put(`${this.baseUrl}/pipelines/${id}`, data);
  }

  deletePipeline(id: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/pipelines/${id}`);
  }

  getPipelineFiles(id: string, kind = 'source'): Observable<any[]> {
    return this.http.get<any[]>(`${this.baseUrl}/pipelines/${id}/files`, { params: { kind } });
  }

  uploadPipelineFile(id: string, filename: string, contentBase64: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/pipelines/${id}/files`, { filename, content_base64: contentBase64 });
  }

  getPipelineFile(fileId: string, sheet?: string | null): Observable<any> {
    const params: any = sheet ? { sheet } : {};
    return this.http.get(`${this.baseUrl}/pipeline-files/${fileId}`, { params });
  }

  pipelineFileDownloadUrl(fileId: string): string {
    return `${this.baseUrl}/pipeline-files/${fileId}/download`;
  }

  getRobotFields(processId: string, versionId?: string | null): Observable<any[]> {
    const params: any = { process_id: processId };
    if (versionId) params.version_id = versionId;
    return this.http.get<any[]>(`${this.baseUrl}/workflow/robot-fields`, { params });
  }

  getProcessSteps(processId: string, versionId?: string | null): Observable<any[]> {
    const params: any = { process_id: processId };
    if (versionId) params.version_id = versionId;
    return this.http.get<any[]>(`${this.baseUrl}/workflow/process-steps`, { params });
  }

  runPipeline(id: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/pipelines/${id}/run`, {});
  }

  getSmtp(): Observable<any> {
    return this.http.get(`${this.baseUrl}/integrations/smtp`);
  }

  saveSmtp(data: any): Observable<any> {
    return this.http.put(`${this.baseUrl}/integrations/smtp`, data);
  }

  testSmtp(to: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/integrations/smtp/test`, { to });
  }

  getPipelineRuns(id: string): Observable<any[]> {
    return this.http.get<any[]>(`${this.baseUrl}/pipelines/${id}/runs`);
  }

  getPipelineRun(runId: string): Observable<any> {
    return this.http.get(`${this.baseUrl}/pipeline-runs/${runId}`);
  }

  cancelPipelineRun(runId: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/pipeline-runs/${runId}/cancel`, {});
  }

  retryFailedPipelineRun(runId: string, nodeId?: string): Observable<any> {
    const params: any = nodeId ? { node_id: nodeId } : {};
    return this.http.post(`${this.baseUrl}/pipeline-runs/${runId}/retry-failed`, {}, { params });
  }

  pipelineRunReportUrl(runId: string): string {
    return `${this.baseUrl}/pipeline-runs/${runId}/report.csv`;
  }

  regeneratePipelineKey(id: string): Observable<{ api_key: string }> {
    return this.http.post<{ api_key: string }>(`${this.baseUrl}/pipelines/${id}/api-key`, {});
  }

  // AI
  aiHealth(): Observable<any> {
    return this.http.get(`${this.baseUrl}/ai/health`);
  }

  aiModels(): Observable<any[]> {
    return this.http.get<any[]>(`${this.baseUrl}/ai/models`);
  }

  aiExecute(request: any): Observable<any> {
    return this.http.post(`${this.baseUrl}/ai/execute`, request);
  }

  // WebSocket for live execution updates
  connectExecutionWs(executionId: string): WebSocket {
    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return new WebSocket(`${wsProto}//${window.location.host}/ws/executions/${executionId}`);
  }
}
