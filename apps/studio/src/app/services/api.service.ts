import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Process, ProcessVersion, Execution, ExecutionStep } from '../models/process.model';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private baseUrl = '/api/v1';

  constructor(private http: HttpClient) {}

  // Processes
  getProcesses(): Observable<Process[]> {
    return this.http.get<Process[]>(`${this.baseUrl}/processes`);
  }

  getProcess(id: string): Observable<Process> {
    return this.http.get<Process>(`${this.baseUrl}/processes/${id}`);
  }

  createProcess(name: string, description?: string): Observable<Process> {
    return this.http.post<Process>(`${this.baseUrl}/processes`, { name, description });
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
  startRecording(processId: string, targetUrl: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/recording/start`, { process_id: processId, target_url: targetUrl });
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
    return this.http.get(`${this.baseUrl}/users/me`);
  }

  // Robots
  getRobots(): Observable<any[]> {
    return this.http.get<any[]>(`${this.baseUrl}/robots`);
  }

  getRobotStats(): Observable<any> {
    return this.http.get(`${this.baseUrl}/robots/stats`);
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
