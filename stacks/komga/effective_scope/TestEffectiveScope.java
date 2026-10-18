import java.nio.file.*;
import java.util.*;

/** JDK-only closure tests. Does not substitute fake Spring/config authority. */
public class TestEffectiveScope {
 static int count;
 static void check(boolean value){if(!value)throw new AssertionError();count++;}
 static void refused(Throwing action,String code)throws Exception{try{action.run();throw new AssertionError("accepted");}catch(IllegalStateException e){check(e.getMessage().equals(code));}}
 interface Throwing{void run()throws Exception;}
 static class FileResource {final java.io.File file;FileResource(String value){file=new java.io.File(value);}public java.io.File getFile(){return file;}}
 static class Hidden {public String value(){return "actual";}}
 public static void main(String[]args)throws Exception{
  KomgaEffectiveScope.declaredLocation("optional:file:/config/application.yml");check(true);
  check(KomgaEffectiveScope.fileResourcePath(new FileResource("./application.xml"),java.net.URI.create("file:./application.xml")).equals(Path.of("./application.xml").toAbsolutePath().normalize()));
  check(KomgaEffectiveScope.fileResourcePath(new FileResource("/config/application.yml"),java.net.URI.create("file:/config/application.yml")).equals(Path.of("/config/application.yml")));
  refused(()->KomgaEffectiveScope.fileResourcePath(new FileResource("/config/application.yml"),java.net.URI.create("https://invalid/application.yml")),"unsupported-resource-scheme");
  KomgaEffectiveScope.declaredLocation("file:/config/");check(true);
  refused(()->KomgaEffectiveScope.declaredLocation("file:/outside/application.yml"),"unsupported-declared-file-location");
  refused(()->KomgaEffectiveScope.declaredLocation("env:EXTERNAL"),"unsupported-import-origin");
  try{TargetEffectiveScopeCase.expectedUnsupported(()->new LinkedHashMap<>());throw new IllegalStateException("bad-fixture-success");}catch(AssertionError expected){check(expected.getMessage().equals("unsupported-tree-accepted"));}
  try{TargetEffectiveScopeCase.expectedUnsupported(()->{throw new ReflectiveOperationException("unrelated-ABI");});throw new AssertionError();}catch(ReflectiveOperationException expected){check(true);}
  check(TargetEffectiveScopeCase.expectedUnsupported(()->{throw new java.lang.reflect.InvocationTargetException(new KomgaEffectiveScope.Held("unclosed-config-origin"));}));
  try{TargetEffectiveScopeCase.expectedUnsupported(()->{throw new KomgaEffectiveScope.Held("config-bound");});throw new AssertionError();}catch(KomgaEffectiveScope.Held expected){check(expected.code.equals("config-bound"));}
  try{TargetEffectiveScopeCase.expectedUnsupported(()->{throw new KomgaEffectiveScope.Held("unsupported-import-origin");});throw new AssertionError();}catch(KomgaEffectiveScope.Held expected){check(expected.code.equals("unsupported-import-origin"));}
  KomgaEffectiveScope.originalPropertyNames=Set.of("user.home","java.io.tmpdir");
  KomgaEffectiveScope.supportedPlaceholders("${user.home}/.komga");check(true);
  KomgaEffectiveScope.supportedPlaceholders("${java.io.tmpdir:/config}/database.sqlite");check(true);
  refused(()->KomgaEffectiveScope.supportedPlaceholders("${os.name:/config}/database.sqlite"),"uncaptured-jvm-placeholder");
  KomgaEffectiveScope.originalPropertyNames=Set.of("user.home");
  refused(()->KomgaEffectiveScope.supportedPlaceholders("${java.io.tmpdir:/config}/database.sqlite"),"uncaptured-jvm-placeholder");
  refused(()->KomgaEffectiveScope.supportedPlaceholders(List.of("${user.language:en}")),"uncaptured-jvm-placeholder");
  refused(()->KomgaEffectiveScope.supportedPlaceholders("${${prefix}:fallback}"),"dynamic-placeholder-key");
  check(KomgaEffectiveScope.heapOnly("-Xms64m -Xmx256m"));check(!KomgaEffectiveScope.heapOnly("-Dsecret=value"));check(!KomgaEffectiveScope.heapOnly("-Xmx1g -javaagent:bad"));
  java.io.PrintStream oldOut=System.out,oldErr=System.err;var protocol=new java.io.ByteArrayOutputStream();var diagnostic=new java.io.ByteArrayOutputStream();
  try{System.setOut(new java.io.PrintStream(protocol));System.setErr(new java.io.PrintStream(diagnostic));java.io.PrintStream expected=System.out;
   String value=KomgaEffectiveScope.frameworkOutput(()->{System.out.print("framework-warning");return "value";});check(value.equals("value")&&System.out==expected&&protocol.size()==0&&diagnostic.toString().equals("framework-warning"));
   try{KomgaEffectiveScope.frameworkOutput(()->{System.out.print("failure-warning");throw new ReflectiveOperationException("synthetic");});throw new AssertionError();}catch(ReflectiveOperationException expectedFailure){check(System.out==expected&&protocol.size()==0&&diagnostic.toString().equals("framework-warningfailure-warning"));}
  }finally{System.setOut(oldOut);System.setErr(oldErr);}
  check(KomgaEffectiveScope.numbers(List.of(1,2L)).equals(List.of(1L,2L)));
  refused(()->KomgaEffectiveScope.numbers(List.of("bad")),"node-number");
  check(KomgaEffectiveScope.call(new Hidden(),"value",new Class<?>[]{}).equals("actual"));
  Path root=Files.createTempDirectory("effective-jdk-only-");
  try{
   Path file=root.resolve("application.yml");Files.writeString(file,"komga: original\n");
   var original=KomgaClasspathMetadata.nine(file,false);
   check(new String(KomgaEffectiveScope.readConfig(file,original),java.nio.charset.StandardCharsets.UTF_8).equals("komga: original\n"));
   KomgaEffectiveScope.FILES.put(file,original);KomgaEffectiveScope.HASHES.put(file,KomgaEffectiveScope.hash(Files.readAllBytes(file)));
   KomgaEffectiveScope.closeFiles();check(true);
   Files.writeString(file,"komga: changed\n");refused(()->KomgaEffectiveScope.closeFiles(),"config-original-final");
   KomgaEffectiveScope.FILES.clear();KomgaEffectiveScope.HASHES.clear();
   Path missing=root.resolve("absent.yml");KomgaEffectiveScope.ABSENT.put(missing,KomgaEffectiveScope.node(KomgaClasspathMetadata.nine(root,false)));
   KomgaEffectiveScope.closeFiles();check(true);Files.writeString(missing,"x");refused(()->KomgaEffectiveScope.closeFiles(),"config-absence-final");KomgaEffectiveScope.ABSENT.clear();
   Path directory=root.resolve("lucene");Files.createDirectory(directory);KomgaEffectiveScope.SCOPE_NODES.put(directory,KomgaEffectiveScope.node(KomgaClasspathMetadata.nine(directory,false)));
   KomgaEffectiveScope.closeFiles();check(true);Files.move(directory,root.resolve("lucene.old"));Files.createDirectory(directory);refused(()->KomgaEffectiveScope.closeFiles(),"scope-node-final");KomgaEffectiveScope.SCOPE_NODES.clear();
   var child=KomgaClasspathMetadata.nine(directory,false);var host=new ArrayList<Long>(KomgaEffectiveScope.node(child));host.set(0,999999L);
   KomgaEffectiveScope.host=new LinkedHashMap<>();KomgaEffectiveScope.host.put("host_path",root.toString());KomgaEffectiveScope.host.put("root_identity",host);KomgaEffectiveScope.host.put("entries",Map.of());
   check(KomgaEffectiveScope.hostNode(Path.of("/config"),child).equals(host));
   host.set(1,host.get(1)+1);refused(()->KomgaEffectiveScope.hostNode(Path.of("/config"),child),"host-child-node-join");
   check(KomgaEffectiveScope.hostPath(Path.of("/config/database.sqlite")).equals(root.resolve("database.sqlite").toString()));
   refused(()->KomgaEffectiveScope.hostPath(Path.of("/outside")),"direct-normal-config-path");
  }finally{try(var walk=Files.walk(root)){for(Path p:walk.sorted(Comparator.reverseOrder()).toList())Files.delete(p);}}
  System.out.println("JDK_CLOSURE_CASES "+count+"; SPRING_REPLAY_CASES 0; CONFIGURED_ACCEPTANCE false");
 }
}
