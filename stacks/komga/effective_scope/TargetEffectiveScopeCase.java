import java.nio.file.*;
import java.util.*;

/** Actual Boot/Komga target fixture, solely disposable /config; never a reader observation. */
public class TargetEffectiveScopeCase {
 static void need(boolean value,String code){if(!value)throw new IllegalStateException(code);}
 static boolean expectedUnsupported(Observation observation)throws Exception{return expectedRefusal(observation,Set.of("unclosed-config-origin"));}
 interface Observation {Map<String,Object> run()throws Exception;}
 static boolean expectedRefusal(Observation observation,Set<String>codes)throws Exception{
  try{observation.run();}
  catch(Exception failure){Throwable cause=KomgaEffectiveScope.unwrap(failure);if(cause instanceof KomgaEffectiveScope.Held&&codes.contains(((KomgaEffectiveScope.Held)cause).code))return true;throw failure;}
  throw new AssertionError("unsupported-tree-accepted");
 }
 public static void main(String[]args)throws Exception{
  need(args.length==1&&Set.of("defaults","precedence","profile","import","unsupported-tree","changed-config","uncaptured-default","explicit-default","inactive-default","heap-env").contains(args[0]),"case");
  Path root=Path.of("/config");try(var entries=Files.list(root)){need(entries.findAny().isEmpty(),"empty-disposable-config-only");}
  List<Path>created=new ArrayList<>();
  try{
   for(String n:List.of("database.sqlite","tasks.sqlite")){Path p=root.resolve(n);Files.write(p,new byte[]{});created.add(p);}
   Path index=root.resolve("lucene");Files.createDirectory(index);created.add(index);
   Map<String,Object>props=new LinkedHashMap<>();props.put("user.dir","/app");props.put("user.home","/nonexistent");props.put("user.name","fixture");props.put("spring.profiles.include","docker");
   Map<String,Object>env=new LinkedHashMap<>();env.put("KOMGA_CONFIGDIR","/config");
   if(args[0].equals("heap-env"))env.put("JAVA_TOOL_OPTIONS","-Xms64m -Xmx256m");
   List<String>cli=new ArrayList<>();cli.add("--spring.config.additional-location=file:/config/");
   String data="komga:\n  database:\n    file: /config/database.sqlite\n";
   if(args[0].equals("precedence")){data="komga:\n  database:\n    file: /config/wrong-file.sqlite\n";env.put("KOMGA_DATABASE_FILE","/config/wrong-env.sqlite");props.put("komga.database.file","/config/wrong-property.sqlite");cli.add("--komga.database.file=/config/database.sqlite");}
   if(args[0].equals("profile")){props.put("spring.profiles.active","fixture");Path extra=root.resolve("application-fixture.yml");Files.writeString(extra,"komga:\n  database:\n    file: /config/database.sqlite\n");created.add(extra);data="komga:\n  database:\n    file: /config/wrong-profile.sqlite\n";}
   if(args[0].equals("import")){Path extra=root.resolve("application-extra.properties");Files.writeString(extra,"komga.database.file=/config/database.sqlite\n");created.add(extra);data="spring:\n  config:\n    import: optional:file:/config/application-extra.properties\n";}
   if(args[0].equals("unsupported-tree")){Path tree=root.resolve("tree");Files.createDirectory(tree);created.add(tree);Path leaf=tree.resolve("komga.database.file");Files.writeString(leaf,"/config/database.sqlite");created.add(leaf);data="spring:\n  config:\n    import: configtree:/config/tree/\n";}
   if(args[0].equals("uncaptured-default")||args[0].equals("explicit-default"))data="komga:\n  database:\n    file: \"${java.io.tmpdir:/config}/database.sqlite\"\n";
   if(args[0].equals("explicit-default"))props.put("java.io.tmpdir","/config");
   if(args[0].equals("inactive-default"))data+="---\nspring:\n  config:\n    activate:\n      on-profile: never-active\nkomga:\n  database:\n    file: \"${java.io.tmpdir:/config}/database.sqlite\"\n";
   Path app=root.resolve("application.yml");Files.writeString(app,data);created.add(app);
   Map<String,Object>entries=new LinkedHashMap<>(),files=new LinkedHashMap<>();
   for(Path p:created){entries.put(p.getFileName().toString(),KomgaEffectiveScope.node(KomgaClasspathMetadata.nine(p,false)));if(p.getParent().equals(root)&&p.getFileName().toString().matches("application.*\\.(yml|properties)"))files.put(p.toString(),Map.of("sha256",KomgaEffectiveScope.hash(Files.readAllBytes(p)),"signature9",KomgaClasspathMetadata.nine(p,false)));}
   Map<String,Object>input=new LinkedHashMap<>();input.put("version",1);input.put("kind","original-komga-effective-input-v1");input.put("properties",props);input.put("environment",env);input.put("args",cli);input.put("config_roots",List.of("/config"));input.put("source_sha256","0".repeat(64));input.put("runtime_sha256","1".repeat(64));input.put("image","fixture-only");input.put("container_id","2".repeat(64));input.put("pid",1);input.put("start_time",1);input.put("mount",Map.of("host_path","/config","root_identity",KomgaEffectiveScope.node(KomgaClasspathMetadata.nine(root,false)),"entries",entries,"config_files",files));
   if(args[0].equals("unsupported-tree")){need(expectedUnsupported(()->KomgaEffectiveScope.collect(input)),"exact-owning-refusal");System.out.println("TARGET_CASE unsupported-tree PASS; CONFIGURED_ACCEPTANCE false");return;}
   if(Set.of("uncaptured-default","inactive-default").contains(args[0])){need(expectedRefusal(()->KomgaEffectiveScope.collect(input),Set.of("uncaptured-jvm-placeholder")),"exact-owning-refusal");System.out.println("TARGET_CASE "+args[0]+" PASS; CONFIGURED_ACCEPTANCE false");return;}
   Map<String,Object>report=KomgaEffectiveScope.collect(input);
   need(report.get("application_context_started").equals(false)&&report.get("scope_observation_verified").equals(false)&&report.get("final_ack_required").equals(true),"no-authority");
   Map<?,?>scopes=(Map<?,?>)report.get("scopes");need(((Map<?,?>)scopes.get("database")).get("host_path").equals("/config/database.sqlite"),"actual-binder-precedence");
   if(args[0].equals("changed-config")){Files.writeString(app,"changed");try{KomgaEffectiveScope.closeFiles();throw new AssertionError("changed-original-accepted");}catch(IllegalStateException expected){need(expected.getMessage().equals("config-original-final"),"actual-original-refusal");}}
   else KomgaEffectiveScope.closeFiles();
   need(Files.size(root.resolve("database.sqlite"))==0&&Files.size(root.resolve("tasks.sqlite"))==0,"no-database-open-or-write");
   System.out.println("TARGET_CASE "+args[0]+" PASS; CONFIGURED_ACCEPTANCE false");
  }finally{for(Path p:created.stream().sorted(Comparator.reverseOrder()).toList())Files.delete(p);try(var left=Files.list(root)){need(left.findAny().isEmpty(),"fixture-cleanup");}}
 }
}
